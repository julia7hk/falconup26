"""Tests for the /api/portfolio endpoints (mocked DB + provider, no network)."""

from __future__ import annotations

from collections import namedtuple
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from db import get_session
from main import app
from market.fetcher import PriceFetcher
from market.models import Quote
from tests.test_fetcher import FakeProvider

client = TestClient(app)

# Named tuples matching the SQL column sets returned by portfolio queries
SymbolIdRow = namedtuple("SymbolIdRow", ["id"])
InsertedRow = namedtuple("InsertedRow", ["id"])  # RETURNING id
HoldingRow = namedtuple(
    "HoldingRow",
    ["id", "ticker", "name", "shares", "avg_cost", "created_at"],
)
PortfolioRow = namedtuple(
    "PortfolioRow",
    ["id", "ticker", "name", "type", "sector", "leverage_factor", "shares", "avg_cost"],
)

NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)

SAMPLE_HOLDING = HoldingRow(
    id=1, ticker="QQQ", name="Invesco QQQ Trust", shares=10, avg_cost=480.0, created_at=NOW,
)

SAMPLE_PORTFOLIO_ROW = PortfolioRow(
    id=1, ticker="QQQ", name="Invesco QQQ Trust", type="etf",
    sector="Technology", leverage_factor=1, shares=10, avg_cost=480.0,
)


def _patched_fetcher():
    return PriceFetcher(FakeProvider())


# ---- helpers to build mock sessions ----


def _mock_session_for_add(symbol_exists: bool = True):
    """Mock session for POST /api/portfolio/holdings."""
    session = AsyncMock()
    call_count = 0

    async def fake_execute(query, params=None):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # symbol lookup
            result.fetchone.return_value = SymbolIdRow(id=1) if symbol_exists else None
        elif call_count == 2:
            # INSERT RETURNING id
            result.scalar.return_value = 1
        else:
            # _get_holding_or_404 after insert
            result.fetchone.return_value = SAMPLE_HOLDING
        return result

    session.execute = fake_execute
    return session


def _mock_session_for_list(rows: list | None = None):
    """Mock session for GET /api/portfolio."""
    session = AsyncMock()

    async def fake_execute(query, params=None):
        result = MagicMock()
        result.fetchall.return_value = rows if rows is not None else [SAMPLE_PORTFOLIO_ROW]
        return result

    session.execute = fake_execute
    return session


def _mock_session_for_update():
    """Mock session for PUT /api/portfolio/holdings/{id}."""
    session = AsyncMock()
    call_count = 0

    async def fake_execute(query, params=None):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        # Both calls to _get_holding_or_404 (before update and after) + the UPDATE itself
        if call_count in (1, 3):
            updated = HoldingRow(
                id=1, ticker="QQQ", name="Invesco QQQ Trust",
                shares=20, avg_cost=480.0, created_at=NOW,
            )
            result.fetchone.return_value = updated if call_count == 3 else SAMPLE_HOLDING
        else:
            result.fetchone.return_value = None  # UPDATE returns nothing we use
        return result

    session.execute = fake_execute
    return session


def _mock_session_for_delete(exists: bool = True):
    """Mock session for DELETE /api/portfolio/holdings/{id}."""
    session = AsyncMock()
    call_count = 0

    async def fake_execute(query, params=None):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.fetchone.return_value = SAMPLE_HOLDING if exists else None
        return result

    session.execute = fake_execute
    return session


# ---- tests ----


class TestAddHolding:
    def _override(self, session):
        async def _gen():
            yield session
        app.dependency_overrides[get_session] = _gen
        return self

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_add_success(self):
        self._override(_mock_session_for_add(symbol_exists=True))
        resp = client.post("/api/portfolio/holdings", json={
            "ticker": "QQQ", "shares": 10, "avg_cost": 480.0,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["ticker"] == "QQQ"
        assert data["shares"] == 10
        assert data["avg_cost"] == 480.0

    def test_add_unknown_symbol(self):
        self._override(_mock_session_for_add(symbol_exists=False))
        resp = client.post("/api/portfolio/holdings", json={
            "ticker": "FAKE", "shares": 5, "avg_cost": 100.0,
        })
        assert resp.status_code == 404

    def test_add_invalid_shares(self):
        self._override(_mock_session_for_add())
        resp = client.post("/api/portfolio/holdings", json={
            "ticker": "QQQ", "shares": -1, "avg_cost": 100.0,
        })
        assert resp.status_code == 422

    def test_add_missing_fields(self):
        self._override(_mock_session_for_add())
        resp = client.post("/api/portfolio/holdings", json={"ticker": "QQQ"})
        assert resp.status_code == 422


class TestGetPortfolio:
    def teardown_method(self):
        app.dependency_overrides.clear()

    @patch("routers.portfolio.get_price_fetcher", _patched_fetcher)
    def test_get_portfolio_with_holdings(self):
        async def _gen():
            yield _mock_session_for_list()
        app.dependency_overrides[get_session] = _gen

        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["holdings"]) == 1
        h = data["holdings"][0]
        assert h["ticker"] == "QQQ"
        assert h["shares"] == 10
        assert h["price"] is not None
        assert h["market_value"] is not None
        assert "total_value" in data

    def test_get_empty_portfolio(self):
        async def _gen():
            yield _mock_session_for_list(rows=[])
        app.dependency_overrides[get_session] = _gen

        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert data["holdings"] == []
        assert data["total_value"] == 0


    @patch("routers.portfolio.get_price_fetcher", _patched_fetcher)
    def test_get_portfolio_prices_complete(self):
        async def _gen():
            yield _mock_session_for_list()
        app.dependency_overrides[get_session] = _gen

        resp = client.get("/api/portfolio")
        data = resp.json()
        assert data["prices_complete"] is True

    def test_get_portfolio_quote_failure_excludes_cost_from_totals(self):
        """When a quote fails, that holding's cost is excluded from totals."""
        def _failing_fetcher():
            provider = MagicMock()
            provider.get_quote.side_effect = RuntimeError("rate limited")
            return PriceFetcher(provider)

        async def _gen():
            yield _mock_session_for_list()
        app.dependency_overrides[get_session] = _gen

        with patch("routers.portfolio.get_price_fetcher", _failing_fetcher):
            resp = client.get("/api/portfolio")

        data = resp.json()
        assert len(data["holdings"]) == 1
        h = data["holdings"][0]
        assert h["price"] is None
        assert h["market_value"] is None
        # Totals should NOT include the failed holding's cost
        assert data["total_value"] == 0
        assert data["total_cost"] == 0
        assert data["total_pnl"] == 0
        assert data["prices_complete"] is False

    def test_get_portfolio_partial_quotes(self):
        """With 2 holdings and 1 quote failure, totals reflect only the priced holding."""
        row2 = PortfolioRow(
            id=2, ticker="SPY", name="SPDR S&P 500", type="etf",
            sector="Broad Market", leverage_factor=1, shares=5, avg_cost=500.0,
        )

        call_count = 0
        def _partial_fetcher():
            provider = MagicMock()
            def _quote(symbol):
                nonlocal call_count
                call_count += 1
                if symbol == "QQQ":
                    return Quote(
                        symbol="QQQ", price=500.0, change=1.0,
                        change_percent=0.2, timestamp=NOW,
                    )
                raise RuntimeError("unknown ticker")
            provider.get_quote.side_effect = _quote
            return PriceFetcher(provider)

        async def _gen():
            yield _mock_session_for_list(rows=[SAMPLE_PORTFOLIO_ROW, row2])
        app.dependency_overrides[get_session] = _gen

        with patch("routers.portfolio.get_price_fetcher", _partial_fetcher):
            resp = client.get("/api/portfolio")

        data = resp.json()
        assert len(data["holdings"]) == 2
        # Only QQQ is priced: 10 shares * $500 = $5000 value, cost = 10 * $480 = $4800
        assert data["total_value"] == 5000.0
        assert data["total_cost"] == 4800.0
        assert data["total_pnl"] == 200.0
        assert data["prices_complete"] is False


class TestAddHoldingMerge:
    """Test that adding a duplicate symbol merges via ON CONFLICT."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_add_duplicate_merges(self):
        """Adding same symbol twice should upsert (weighted avg cost)."""
        session = AsyncMock()
        call_count = 0

        async def fake_execute(query, params=None):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # symbol lookup
                result.fetchone.return_value = SymbolIdRow(id=1)
            elif call_count == 2:
                # UPSERT RETURNING id — returns the existing row id
                result.scalar.return_value = 1
            else:
                # _get_holding_or_404
                merged = HoldingRow(
                    id=1, ticker="QQQ", name="Invesco QQQ Trust",
                    shares=20, avg_cost=490.0, created_at=NOW,
                )
                result.fetchone.return_value = merged
            return result

        session.execute = fake_execute

        async def _gen():
            yield session
        app.dependency_overrides[get_session] = _gen

        resp = client.post("/api/portfolio/holdings", json={
            "ticker": "QQQ", "shares": 10, "avg_cost": 500.0,
        })
        assert resp.status_code == 201
        data = resp.json()
        # The mock returns the merged result
        assert data["shares"] == 20
        assert data["avg_cost"] == 490.0


class TestUpdateHolding:
    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_update_shares(self):
        async def _gen():
            yield _mock_session_for_update()
        app.dependency_overrides[get_session] = _gen

        resp = client.put("/api/portfolio/holdings/1", json={"shares": 20})
        assert resp.status_code == 200
        assert resp.json()["shares"] == 20

    def test_update_nothing(self):
        async def _gen():
            yield _mock_session_for_update()
        app.dependency_overrides[get_session] = _gen

        resp = client.put("/api/portfolio/holdings/1", json={})
        assert resp.status_code == 400


class TestDeleteHolding:
    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_delete_success(self):
        async def _gen():
            yield _mock_session_for_delete(exists=True)
        app.dependency_overrides[get_session] = _gen

        resp = client.delete("/api/portfolio/holdings/1")
        assert resp.status_code == 204

    def test_delete_not_found(self):
        async def _gen():
            yield _mock_session_for_delete(exists=False)
        app.dependency_overrides[get_session] = _gen

        resp = client.delete("/api/portfolio/holdings/999")
        assert resp.status_code == 404
