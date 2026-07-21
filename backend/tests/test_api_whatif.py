"""Tests for POST /api/portfolio/what-if (mocked DB + quotes, no network).

The endpoint fetches raw materials via several SQL queries (holdings, optional
extra-symbol lookup, SPY id, price history), so the mock session dispatches on
the SQL text rather than call order — the extra-symbol query only fires for a
buy of an unheld symbol.
"""

from __future__ import annotations

from collections import namedtuple
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from auth import get_current_user
from db import get_session
from main import app
from market.fetcher import PriceFetcher
from tests.test_fetcher import FakeProvider

FAKE_USER = {"id": "test-user-1", "name": "Test User", "email": "test@test.com"}

client = TestClient(app)

# Column sets matching the SQL in _fetch_market_data
HeldRow = namedtuple(
    "HeldRow",
    ["id", "symbol_id", "ticker", "name", "sector", "leverage_factor", "shares", "avg_cost"],
)
ExtraRow = namedtuple("ExtraRow", ["symbol_id", "ticker", "name", "sector", "leverage_factor"])
SpyRow = namedtuple("SpyRow", ["id"])

# Two current holdings: QQQ (1x tech) and TQQQ (3x tech)
QQQ = HeldRow(1, 1, "QQQ", "Invesco QQQ", "Technology", 1.0, 10, 480.0)
TQQQ = HeldRow(2, 2, "TQQQ", "ProShares UltraPro QQQ", "Technology", 3.0, 5, 60.0)

# Extra symbols resolvable for buys of unheld tickers
SOXL = ExtraRow(3, "SOXL", "Direxion Semi Bull 3x", "Technology", 3.0)


def _patched_fetcher():
    """FakeProvider quotes every symbol at $100."""
    return PriceFetcher(FakeProvider())


def _mock_session(held: list, extra: list | None = None, spy: bool = True):
    """Dispatch on SQL text: holdings / extra-symbol / SPY id / price history."""
    session = AsyncMock()

    async def fake_execute(query, params=None):
        sql = str(query)
        result = MagicMock()
        if "portfolio_holding" in sql:
            result.fetchall.return_value = held
        elif "ticker = ANY(:tickers)" in sql:
            result.fetchall.return_value = extra or []
        elif "ticker = 'SPY'" in sql:
            result.fetchone.return_value = SpyRow(id=99) if spy else None
        elif "price_history" in sql:
            result.fetchall.return_value = []  # no history: beta/drawdown/grade -> None
        else:
            result.fetchall.return_value = []
            result.fetchone.return_value = None
        return result

    session.execute = fake_execute
    return session


def _override(session):
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER

    async def _gen():
        yield session

    app.dependency_overrides[get_session] = _gen


def _post(**body):
    with patch("routers.risk.get_price_fetcher", _patched_fetcher):
        return client.post("/api/portfolio/what-if", json=body)


class TestWhatIf:
    def teardown_method(self):
        app.dependency_overrides.clear()

    # ---- auth + input validation ----

    def test_requires_auth(self):
        # No auth override + no cookie -> get_current_user raises 401 before
        # the endpoint body runs. get_session still needs overriding so the
        # dependency resolves.
        async def _gen():
            yield _mock_session([QQQ])

        app.dependency_overrides[get_session] = _gen
        resp = client.post(
            "/api/portfolio/what-if", json={"ticker": "QQQ", "action": "buy", "quantity": 1}
        )
        assert resp.status_code == 401

    def test_invalid_quantity_rejected(self):
        _override(_mock_session([QQQ]))
        resp = _post(ticker="QQQ", action="buy", quantity=-5)
        assert resp.status_code == 422

    def test_invalid_action_rejected(self):
        _override(_mock_session([QQQ]))
        resp = _post(ticker="QQQ", action="yolo", quantity=1)
        assert resp.status_code == 422

    def test_unknown_symbol_404(self):
        # Buying a symbol not held and not resolvable as an extra -> 404
        _override(_mock_session([QQQ], extra=[]))
        resp = _post(ticker="FAKE", action="buy", quantity=1)
        assert resp.status_code == 404

    # ---- buy ----

    def test_buy_more_of_held(self):
        _override(_mock_session([QQQ, TQQQ]))
        resp = _post(ticker="QQQ", action="buy", quantity=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["trade"] == {"ticker": "QQQ", "action": "buy", "quantity": 10}
        assert data["before"]["holdings_count"] == 2
        assert data["after"]["holdings_count"] == 2  # same symbols, shifted weights
        # Buying more of the 1x holding dilutes the 3x -> leverage should fall
        lev = data["diff"]["effective_leverage"]
        assert lev["after"] < lev["before"]
        assert lev["direction"] == "improved"

    def test_buy_unheld_symbol_appends(self):
        _override(_mock_session([QQQ], extra=[SOXL]))
        resp = _post(ticker="SOXL", action="buy", quantity=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["before"]["holdings_count"] == 1
        assert data["after"]["holdings_count"] == 2

    def test_empty_portfolio_buy(self):
        _override(_mock_session([], extra=[SOXL]))
        resp = _post(ticker="SOXL", action="buy", quantity=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["before"]["holdings_count"] == 0
        assert data["after"]["holdings_count"] == 1

    # ---- sell ----

    def test_sell_partial_keeps_holding(self):
        _override(_mock_session([QQQ, TQQQ]))
        resp = _post(ticker="TQQQ", action="sell", quantity=2)
        assert resp.status_code == 200
        data = resp.json()
        assert data["after"]["holdings_count"] == 2  # still owns some TQQQ

    def test_sell_to_zero_removes_holding(self):
        _override(_mock_session([QQQ, TQQQ]))
        resp = _post(ticker="TQQQ", action="sell", quantity=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["after"]["holdings_count"] == 1  # TQQQ fully sold, dropped
        # Selling all the 3x leaves only the 1x -> leverage improves
        lev = data["diff"]["effective_leverage"]
        assert lev["direction"] == "improved"

    def test_oversell_rejected(self):
        _override(_mock_session([QQQ, TQQQ]))
        resp = _post(ticker="QQQ", action="sell", quantity=999)
        assert resp.status_code == 400

    def test_sell_not_owned_rejected(self):
        # SOXL is resolvable (extra) so it's a real symbol, but not held -> 400
        _override(_mock_session([QQQ], extra=[SOXL]))
        resp = _post(ticker="SOXL", action="sell", quantity=1)
        assert resp.status_code == 400

    # ---- diff shape ----

    def test_diff_shape(self):
        _override(_mock_session([QQQ, TQQQ]))
        resp = _post(ticker="QQQ", action="buy", quantity=1)
        diff = resp.json()["diff"]
        for metric in (
            "concentration",
            "effective_leverage",
            "portfolio_beta",
            "max_drawdown",
            "risk_grade",
        ):
            assert metric in diff
            entry = diff[metric]
            assert set(entry) >= {"before", "after", "delta", "direction"}
            assert entry["direction"] in {
                "improved",
                "worsened",
                "unchanged",
                "unavailable",
            }
