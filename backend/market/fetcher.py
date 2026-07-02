"""High-level price fetcher — the only thing the rest of the app imports.

Wraps a DataProvider with caching. To switch data sources, change the
provider class in get_price_fetcher().
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache

from market.cache import TTLCache
from market.models import OHLCV, Quote
from market.provider import DataProvider
from market.yfinance_provider import YFinanceProvider

# Cache TTLs in seconds
_QUOTE_TTL = 60  # current price: 1 min
_HISTORY_TTL = 3600  # daily bars: 1 hour (only changes after market close)
_SEARCH_TTL = 86400  # symbol search: 24 hours


class PriceFetcher:
    """Cached wrapper around any DataProvider."""

    def __init__(self, provider: DataProvider) -> None:
        self._provider = provider
        self._cache = TTLCache()

    def get_quote(self, symbol: str) -> Quote:
        symbol = symbol.upper()
        key = f"quote:{symbol}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        quote = self._provider.get_quote(symbol)
        self._cache.set(key, quote, ttl=_QUOTE_TTL)
        return quote

    def get_history(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> list[OHLCV]:
        symbol = symbol.upper()
        key = f"history:{symbol}:{start}:{end}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        bars = self._provider.get_history(symbol, start, end)
        self._cache.set(key, bars, ttl=_HISTORY_TTL)
        return bars

    def search_symbols(self, query: str) -> list[dict]:
        key = f"search:{query.lower()}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        results = self._provider.search_symbols(query)
        self._cache.set(key, results, ttl=_SEARCH_TTL)
        return results


@lru_cache(maxsize=1)
def get_price_fetcher() -> PriceFetcher:
    """Singleton PriceFetcher. Change the provider class here to switch data sources."""
    return PriceFetcher(provider=YFinanceProvider())
