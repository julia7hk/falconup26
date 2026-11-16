"""Tests for the /api/symbols/{ticker}/indicators endpoint."""

from __future__ import annotations

from collections import namedtuple
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from db import get_session
from main import app

client = TestClient(app)

# Fake row shape matching the SQL query in routers/indicators.py
PriceRow = namedtuple(
    "PriceRow",
    ["date", "symbol_close", "symbol_high", "symbol_low", "spy_close"],
)
MacroRow = namedtuple("MacroRow", ["value"])


def _make_price_rows(n: int = 300) -> list[PriceRow]:
    """Generate n days of synthetic price data."""
    base_date = date.today() - timedelta(days=n)
    rows = []
    for i in range(n):
        price = 100.0 + i * 0.1
        rows.append(
            PriceRow(
                date=base_date + timedelta(days=i),
                symbol_close=price,
                symbol_high=price + 1.0,
                symbol_low=price - 1.0,
                spy_close=100.0 + i * 0.05,
            )
        )
    return rows


def _mock_session(ticker_rows: str = "QQQ"):
    """Create a mock AsyncSession that returns synthetic data."""
    session = AsyncMock()
    call_count = 0

    async def fake_execute(query, params=None):
        nonlocal call_count
        call_count += 1
        # Use MagicMock (not AsyncMock) because SQLAlchemy's fetchall/fetchone
        # are sync methods on the CursorResult object.
        result = MagicMock()
        # First call = price history, second call = macro_history
        if call_count == 1:
            if params and params.get("ticker") == "NOTREAL":
                result.fetchall.return_value = []
            else:
                result.fetchall.return_value = _make_price_rows()
        else:
            result.fetchone.return_value = MacroRow(value=5.33)
        return result

    session.execute = fake_execute
    return session


async def _override_get_session():
    yield _mock_session()


@pytest.fixture(autouse=True)
def _override_db():
    app.dependency_overrides[get_session] = _override_get_session
    yield
    app.dependency_overrides.clear()


def test_indicators_success():
    resp = client.get("/api/symbols/QQQ/indicators")
    assert resp.status_code == 200
    data = resp.json()

    assert data["ticker"] == "QQQ"
    assert "computed_at" in data
    assert data["data_points"] == 300

    # All 9 indicators should be present
    indicators = data["indicators"]
    assert "rsi" in indicators
    assert "macd" in indicators
    assert "bollinger" in indicators
    assert "sma_crossover" in indicators
    assert "atr" in indicators
    assert "beta" in indicators
    assert "sharpe" in indicators
    assert "sortino" in indicators
    assert "max_drawdown" in indicators

    # Composite should be present with required fields
    composite = data["composite"]
    assert composite["signal"] in ("buy", "hold", "sell")
    assert -1 <= composite["score"] <= 1
    assert 0 <= composite["confidence"] <= 1
    assert "contributions" in composite


def test_indicators_unknown_ticker():
    resp = client.get("/api/symbols/NOTREAL/indicators")
    assert resp.status_code == 404


def test_indicators_response_shape():
    """Verify each indicator has the expected fields."""
    resp = client.get("/api/symbols/QQQ/indicators")
    data = resp.json()
    indicators = data["indicators"]

    assert "value" in indicators["rsi"]
    assert "signal" in indicators["rsi"]

    assert "macd_line" in indicators["macd"]
    assert "signal_line" in indicators["macd"]
    assert "histogram" in indicators["macd"]

    assert "width" in indicators["bollinger"]
    assert "upper" in indicators["bollinger"]
    assert "lower" in indicators["bollinger"]

    assert "sma_50" in indicators["sma_crossover"]
    assert "sma_200" in indicators["sma_crossover"]
    assert "crossover_type" in indicators["sma_crossover"]

    assert "value" in indicators["atr"]
    assert "atr_percent" in indicators["atr"]

    assert "value" in indicators["beta"]
    assert "interpretation" in indicators["beta"]

    assert "value" in indicators["sharpe"]
    assert "risk_free_rate" in indicators["sharpe"]


# --- data vintage / staleness -------------------------------------------


def _stale_session(days_ago: int):
    """Mock session whose price history ends `days_ago` days before today."""
    rows = _make_price_rows()
    shift = timedelta(days=days_ago - 1)
    shifted = [r._replace(date=r.date - shift) for r in rows]

    session = AsyncMock()
    call_count = 0

    async def fake_execute(query, params=None):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.fetchall.return_value = shifted
        else:
            result.fetchone.return_value = MacroRow(value=5.33)
        return result

    session.execute = fake_execute
    return session


def _use_session(session):
    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override


def test_indicators_report_data_vintage():
    """Fresh data reports its last bar date and is not flagged stale."""
    resp = client.get("/api/symbols/QQQ/indicators")
    data = resp.json()

    # The default fixture's series ends yesterday.
    assert data["data_through"] == (date.today() - timedelta(days=1)).isoformat()
    assert data["data_age_days"] == 1
    assert data["stale"] is False


def test_indicators_flag_stale_data():
    """A series that stopped updating is flagged, not silently served."""
    _use_session(_stale_session(90))
    resp = client.get("/api/symbols/QQQ/indicators")
    data = resp.json()

    assert data["data_age_days"] == 90
    assert data["stale"] is True
    # computed_at still reports when the math ran — the two must not be conflated.
    assert data["computed_at"] == date.today().isoformat()
    assert data["data_through"] != data["computed_at"]


def test_indicators_weekend_gap_is_not_stale():
    """A long weekend is normal market behaviour, not staleness."""
    _use_session(_stale_session(4))
    resp = client.get("/api/symbols/QQQ/indicators")
    data = resp.json()

    assert data["data_age_days"] == 4
    assert data["stale"] is False
