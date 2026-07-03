"""Tests for PriceFetcher (with a fake provider, no network calls)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from market.fetcher import PriceFetcher
from market.models import OHLCV, Quote, SectorInfo


class FakeProvider:
    """Minimal DataProvider that returns canned data."""

    def __init__(self):
        self.quote_calls = 0
        self.history_calls = 0
        self.sector_calls = 0

    def get_quote(self, symbol: str) -> Quote:
        self.quote_calls += 1
        return Quote(
            symbol=symbol.upper(),
            price=100.0,
            change=1.5,
            change_percent=1.52,
            timestamp=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

    def get_history(self, symbol: str, start: date, end: date) -> list[OHLCV]:
        self.history_calls += 1
        return [
            OHLCV(date=date(2026, 7, 1), open=99.0, high=101.0, low=98.5, close=100.0, volume=1000000),
        ]

    def search_symbols(self, query: str) -> list[dict]:
        return [{"symbol": "QQQ", "name": "Invesco QQQ Trust"}]

    def get_sector_info(self, symbol: str) -> SectorInfo:
        self.sector_calls += 1
        return SectorInfo(symbol=symbol.upper(), sector="Technology", industry="Broad Market Tech ETF", is_etf=True)


def test_get_quote():
    provider = FakeProvider()
    fetcher = PriceFetcher(provider)
    quote = fetcher.get_quote("qqq")
    assert quote.symbol == "QQQ"
    assert quote.price == 100.0


def test_quote_is_cached():
    provider = FakeProvider()
    fetcher = PriceFetcher(provider)
    fetcher.get_quote("QQQ")
    fetcher.get_quote("QQQ")
    assert provider.quote_calls == 1  # second call served from cache


def test_get_history():
    provider = FakeProvider()
    fetcher = PriceFetcher(provider)
    bars = fetcher.get_history("QQQ", date(2026, 1, 1), date(2026, 7, 1))
    assert len(bars) == 1
    assert bars[0].close == 100.0


def test_history_is_cached():
    provider = FakeProvider()
    fetcher = PriceFetcher(provider)
    start, end = date(2026, 1, 1), date(2026, 7, 1)
    fetcher.get_history("QQQ", start, end)
    fetcher.get_history("QQQ", start, end)
    assert provider.history_calls == 1


def test_search():
    provider = FakeProvider()
    fetcher = PriceFetcher(provider)
    results = fetcher.search_symbols("qqq")
    assert results[0]["symbol"] == "QQQ"


def test_get_sector_info():
    provider = FakeProvider()
    fetcher = PriceFetcher(provider)
    info = fetcher.get_sector_info("qqq")
    assert info.symbol == "QQQ"
    assert info.sector == "Technology"
    assert info.is_etf is True


def test_sector_info_is_cached():
    provider = FakeProvider()
    fetcher = PriceFetcher(provider)
    fetcher.get_sector_info("QQQ")
    fetcher.get_sector_info("QQQ")
    assert provider.sector_calls == 1
