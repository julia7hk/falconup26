"""Backfill price_history and macro_history tables from yfinance + FRED.

Pulls 5 years of daily OHLCV for every symbol in the symbol table,
and 5 years of daily values for each FRED macro series.

Usage:
    uv run python -m scripts.backfill
"""

import asyncio
from datetime import date, timedelta

from sqlalchemy import text

from db import async_session
from market.yfinance_provider import YFinanceProvider
from market.fred import SERIES, FredProvider

YEARS = 5


async def backfill_prices(provider: YFinanceProvider) -> int:
    end = date.today()
    start = end - timedelta(days=YEARS * 365)
    rows_inserted = 0

    async with async_session() as session:
        result = await session.execute(text("SELECT id, ticker FROM symbol"))
        symbols = result.fetchall()

    for symbol_id, ticker in symbols:
        print(f"  {ticker}...", end=" ", flush=True)
        bars = provider.get_history(ticker, start, end)
        if not bars:
            print("no data")
            continue

        async with async_session() as session:
            for bar in bars:
                await session.execute(
                    text("""
                        INSERT INTO price_history (symbol_id, date, open, high, low, close, volume)
                        VALUES (:symbol_id, :date, :open, :high, :low, :close, :volume)
                        ON CONFLICT (symbol_id, date) DO NOTHING
                    """),
                    {
                        "symbol_id": symbol_id,
                        "date": bar.date,
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                    },
                )
            await session.commit()
            rows_inserted += len(bars)
        print(f"{len(bars)} bars")

    return rows_inserted


async def backfill_macro(provider: FredProvider) -> int:
    end = date.today()
    start = end - timedelta(days=YEARS * 365)
    rows_inserted = 0

    for series_key, series_id in SERIES.items():
        print(f"  {series_key} ({series_id})...", end=" ", flush=True)
        data = provider.get_series_history(series_key, start, end)
        if not data:
            print("no data")
            continue

        async with async_session() as session:
            for point in data:
                await session.execute(
                    text("""
                        INSERT INTO macro_history (series, date, value)
                        VALUES (:series, :date, :value)
                        ON CONFLICT (series, date) DO NOTHING
                    """),
                    {
                        "series": series_key,
                        "date": date.fromisoformat(point["date"]),
                        "value": point["value"],
                    },
                )
            await session.commit()
            rows_inserted += len(data)
        print(f"{len(data)} points")

    return rows_inserted


async def main():
    print("Backfilling price history (5 years)...")
    yf_provider = YFinanceProvider()
    price_rows = await backfill_prices(yf_provider)
    print(f"Price history: {price_rows} rows inserted\n")

    print("Backfilling macro history (5 years)...")
    fred_provider = FredProvider()
    macro_rows = await backfill_macro(fred_provider)
    print(f"Macro history: {macro_rows} rows inserted\n")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
