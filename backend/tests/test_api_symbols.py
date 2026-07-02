"""Tests for the /api/symbols endpoints (mocked provider, no network)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from market.fetcher import PriceFetcher
from market.models import OHLCV, Quote
from tests.test_fetcher import FakeProvider

client = TestClient(app)


def _patched_fetcher():
    return PriceFetcher(FakeProvider())


@patch("routers.symbols.get_price_fetcher", _patched_fetcher)
def test_search():
    resp = client.get("/api/symbols/search", params={"q": "qqq"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["symbol"] == "QQQ"


@patch("routers.symbols.get_price_fetcher", _patched_fetcher)
def test_get_quote():
    resp = client.get("/api/symbols/QQQ/quote")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "QQQ"
    assert data["price"] == 100.0


@patch("routers.symbols.get_price_fetcher", _patched_fetcher)
def test_get_history():
    resp = client.get("/api/symbols/QQQ/history", params={"days": 30})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert "close" in data[0]


def test_search_requires_query():
    resp = client.get("/api/symbols/search")
    assert resp.status_code == 422  # missing required param
