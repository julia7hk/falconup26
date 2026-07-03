"""Abstract data provider protocol.

Any market data source (yfinance, Twelve Data, Finnhub, etc.) implements
this protocol. 
"""
# rest of the app never imports a concrete provider directly
# all data providers are of class type DataProvider
# to switch, change one line in fetcher.py.


from __future__ import annotations

from datetime import date
from typing import Protocol

from market.models import OHLCV, Quote, SectorInfo


class DataProvider(Protocol):
    """Interface that all market data providers must satisfy."""

    def get_quote(self, symbol: str) -> Quote:
        """Fetch current price snapshot."""
        ...

    def get_history(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> list[OHLCV]:
        """Fetch daily OHLCV bars for the given date range (inclusive)."""
        ...

    def search_symbols(self, query: str) -> list[dict]:
        """Search for symbols matching a query string.

        Returns a list of dicts with at least 'symbol' and 'name' keys.
        """
        ...

    def get_sector_info(self, symbol: str) -> SectorInfo:
        """Fetch sector/industry classification for a symbol."""
        ...
