"""Tests for FRED provider (mocked, no API key needed)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from market.fred import FredProvider, MacroSnapshot


@pytest.fixture
def provider():
    """FredProvider with a mocked fredapi.Fred client."""
    with patch("market.fred.Fred") as MockFred:
        mock_fred = MockFred.return_value
        # Default: return a series with one value
        mock_fred.get_series.return_value = pd.Series(
            [4.33], index=pd.to_datetime(["2026-07-01"])
        )
        p = FredProvider(api_key="test-key")
        yield p


def test_get_risk_free_rate(provider):
    rate = provider.get_risk_free_rate()
    assert rate == 4.33


def test_get_vix(provider):
    vix = provider.get_vix()
    assert vix == 4.33  # same mock, just checking it calls correctly


def test_get_snapshot(provider):
    snap = provider.get_snapshot()
    assert isinstance(snap, MacroSnapshot)
    assert snap.fed_funds_rate == 4.33
    assert snap.as_of == date.today()


def test_get_series_history(provider):
    provider._fred.get_series.return_value = pd.Series(
        [4.30, 4.31, 4.33],
        index=pd.to_datetime(["2026-06-29", "2026-06-30", "2026-07-01"]),
    )
    data = provider.get_series_history("fed_funds_rate", date(2026, 6, 1), date(2026, 7, 1))
    assert len(data) == 3
    assert data[-1]["value"] == 4.33
    assert data[-1]["date"] == "2026-07-01"


def test_unknown_series_raises(provider):
    with pytest.raises(ValueError, match="Unknown series"):
        provider.get_series_history("fake_series", date(2026, 1, 1), date(2026, 7, 1))


def test_empty_series_returns_none(provider):
    provider._fred.get_series.return_value = pd.Series([], dtype=float)
    assert provider.get_risk_free_rate() is None


def test_missing_api_key_raises():
    with patch.dict("os.environ", {"FRED_API_KEY": ""}, clear=False):
        with pytest.raises(ValueError, match="FRED_API_KEY is required"):
            FredProvider(api_key="")


def test_results_are_cached(provider):
    provider.get_risk_free_rate()
    provider.get_risk_free_rate()
    # Fred.get_series should only be called once (second call hits cache)
    assert provider._fred.get_series.call_count == 1
