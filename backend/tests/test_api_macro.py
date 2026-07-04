"""Tests for /api/macro endpoints (mocked FRED, no API key needed)."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from main import app
from market.fred import FredProvider

client = TestClient(app)


def _make_mock_provider():
    with patch("market.fred.Fred") as MockFred:
        mock_fred = MockFred.return_value
        mock_fred.get_series.return_value = pd.Series(
            [4.33], index=pd.to_datetime(["2026-07-01"])
        )
        return FredProvider(api_key="test-key")


@patch("routers.macro.get_fred_provider")
def test_snapshot(mock_get):
    mock_get.return_value = _make_mock_provider()
    resp = client.get("/api/macro/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert "fed_funds_rate" in data
    assert "vix" in data
    assert data["fed_funds_rate"] == 4.33


@patch("routers.macro.get_fred_provider")
def test_risk_free_rate(mock_get):
    mock_get.return_value = _make_mock_provider()
    resp = client.get("/api/macro/risk-free-rate")
    assert resp.status_code == 200
    assert resp.json()["rate"] == 4.33


@patch("routers.macro.get_fred_provider")
def test_vix(mock_get):
    mock_get.return_value = _make_mock_provider()
    resp = client.get("/api/macro/vix")
    assert resp.status_code == 200
    assert resp.json()["vix"] == 4.33


@patch("routers.macro.get_fred_provider")
def test_history(mock_get):
    provider = _make_mock_provider()
    provider._fred.get_series.return_value = pd.Series(
        [4.30, 4.33], index=pd.to_datetime(["2026-06-30", "2026-07-01"])
    )
    mock_get.return_value = provider
    resp = client.get("/api/macro/history/fed_funds_rate", params={"days": 30})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@patch("routers.macro.get_fred_provider")
def test_history_invalid_series(mock_get):
    mock_get.return_value = _make_mock_provider()
    resp = client.get("/api/macro/history/not_real")
    assert resp.status_code == 400
