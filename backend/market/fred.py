"""FRED (Federal Reserve Economic Data) integration.

Fetches macro data: fed funds rate (risk-free rate for Sharpe ratio),
VIX (market fear gauge), and treasury yields.

Requires FRED_API_KEY env var. Get one free at:
https://fred.stlouisfed.org/docs/api/api_key.html
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache

from fredapi import Fred

from market.cache import TTLCache

# FRED series IDs
SERIES = {
    "fed_funds_rate": "DFF",        # Daily Federal Funds Effective Rate
    "vix": "VIXCLS",                # CBOE Volatility Index
    "treasury_3mo": "DGS3MO",       # 3-Month Treasury Yield
    "treasury_2y": "DGS2",          # 2-Year Treasury Yield
    "treasury_10y": "DGS10",        # 10-Year Treasury Yield
    "treasury_30y": "DGS30",        # 30-Year Treasury Yield
}


_CACHE_TTL = 3600  # 1 hour — these values change at most once per day


@dataclass(frozen=True, slots=True)
class MacroSnapshot:
    """Current macro indicators from FRED."""

    fed_funds_rate: float | None
    vix: float | None
    treasury_3mo: float | None
    treasury_2y: float | None
    treasury_10y: float | None
    treasury_30y: float | None
    as_of: date


class FredProvider:
    """Fetches macro data from the FRED API."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("FRED_API_KEY", "")
        if not key:
            raise ValueError(
                "FRED_API_KEY is required. Get one free at "
                "https://fred.stlouisfed.org/docs/api/api_key.html"
            )
        self._fred = Fred(api_key=key)
        self._cache = TTLCache(default_ttl=_CACHE_TTL)

    def _get_latest(self, series_id: str) -> float | None:
        """Fetch the most recent non-null value for a FRED series."""
        key = f"fred:{series_id}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        series = self._fred.get_series(series_id, observation_start="2020-01-01")
        if series is None or series.empty:
            return None
        # Drop NaN values (FRED uses '.' for missing) and get the last one
        series = series.dropna()
        if series.empty:
            return None
        value = round(float(series.iloc[-1]), 4)
        self._cache.set(key, value, ttl=_CACHE_TTL)
        return value

    def get_risk_free_rate(self) -> float | None:
        """Current fed funds rate (annualized %). Used for Sharpe ratio."""
        return self._get_latest(SERIES["fed_funds_rate"])

    def get_vix(self) -> float | None:
        """Current VIX level."""
        return self._get_latest(SERIES["vix"])

    def get_snapshot(self) -> MacroSnapshot:
        """Fetch all macro indicators at once."""
        return MacroSnapshot(
            fed_funds_rate=self._get_latest(SERIES["fed_funds_rate"]),
            vix=self._get_latest(SERIES["vix"]),
            treasury_3mo=self._get_latest(SERIES["treasury_3mo"]),
            treasury_2y=self._get_latest(SERIES["treasury_2y"]),
            treasury_10y=self._get_latest(SERIES["treasury_10y"]),
            treasury_30y=self._get_latest(SERIES["treasury_30y"]),
            as_of=date.today(),
        )

    def get_series_history(
        self,
        series_key: str,
        start: date,
        end: date,
    ) -> list[dict]:
        """Fetch historical values for a named series (e.g. 'vix', 'fed_funds_rate')."""
        series_id = SERIES.get(series_key)
        if series_id is None:
            raise ValueError(f"Unknown series: {series_key}. Valid keys: {list(SERIES.keys())}")
        data = self._fred.get_series(
            series_id,
            observation_start=start.isoformat(),
            observation_end=end.isoformat(),
        )
        if data is None or data.empty:
            return []
        data = data.dropna()
        return [
            {"date": idx.date().isoformat(), "value": round(float(val), 4)}
            for idx, val in data.items()
        ]


@lru_cache(maxsize=1)
def get_fred_provider() -> FredProvider:
    """Singleton FredProvider."""
    return FredProvider()
