"""Fill price_history and macro_history from yfinance + FRED.

Runs in two modes, chosen per symbol/series from what is already stored:

  * nothing stored  -> pull the full 5 years
  * something stored -> pull from a short overlap before the newest stored date

The overlap re-reads the most recent bars so that provisional values and
split/dividend restatements (yfinance serves adjusted prices, which get
revised by later corporate actions) can be written back.

`--full` forces the 5-year window for everything. That is the weekly repair
pass: it restates history after corporate actions and fills any hole a failed
run left behind, so the nightly job can stay a dumb delta.

Usage:
    uv run python -m scripts.backfill           # nightly catch-up
    uv run python -m scripts.backfill --full    # weekly full restatement
"""

import argparse
import asyncio
import sys
from datetime import date, timedelta

from sqlalchemy import text

from db import async_session
from market.yfinance_provider import YFinanceProvider
from market.fred import SERIES, FredProvider

YEARS = 5
OVERLAP_DAYS = 7


def fetch_window(
    last_stored: date | None,
    today: date,
    *,
    full: bool = False,
) -> tuple[date, date]:
    """Date range to pull for one symbol or series.

    A gap of any size is handled by the same rule — a symbol 16 days behind
    and one a day behind differ only in the arithmetic. `min(last_stored,
    today)` keeps the window sane if a stored date is somehow in the future.
    """
    if full or last_stored is None:
        return today - timedelta(days=YEARS * 365), today
    return min(last_stored, today) - timedelta(days=OVERLAP_DAYS), today


# `xmax = 0` is true only for a freshly inserted row, so RETURNING it
# separates inserts from revisions. The WHERE on DO UPDATE skips no-op
# writes, which keeps "revised" meaningful instead of counting the whole
# overlap window every night.
#
# Expect a noise floor of roughly 150 revisions on a --full run. yfinance's
# adjusted prices are not bit-stable across calls (~740 of 1255 QQQ bars
# differ in the raw floats between two identical requests, at ~1e-5 relative);
# rounding to cents absorbs nearly all of it, but a handful per symbol sit on
# a rounding boundary and flip by 0.01. That is the source data, not this
# script. A real corporate-action restatement looks nothing like it — far more
# rows, and far bigger than a cent.
_UPSERT_PRICE = text("""
    INSERT INTO price_history (symbol_id, date, open, high, low, close, volume)
    VALUES (:symbol_id, :date, :open, :high, :low, :close, :volume)
    ON CONFLICT (symbol_id, date) DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        volume = EXCLUDED.volume
    WHERE price_history.open   IS DISTINCT FROM EXCLUDED.open
       OR price_history.high   IS DISTINCT FROM EXCLUDED.high
       OR price_history.low    IS DISTINCT FROM EXCLUDED.low
       OR price_history.close  IS DISTINCT FROM EXCLUDED.close
       OR price_history.volume IS DISTINCT FROM EXCLUDED.volume
    RETURNING (xmax = 0) AS inserted
""")

_UPSERT_MACRO = text("""
    INSERT INTO macro_history (series, date, value)
    VALUES (:series, :date, :value)
    ON CONFLICT (series, date) DO UPDATE SET
        value = EXCLUDED.value
    WHERE macro_history.value IS DISTINCT FROM EXCLUDED.value
    RETURNING (xmax = 0) AS inserted
""")


async def refresh_prices(provider: YFinanceProvider, *, full: bool) -> tuple[int, int]:
    today = date.today()
    inserted = revised = 0

    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT s.id, s.ticker, MAX(ph.date) AS last_stored
                FROM symbol s
                LEFT JOIN price_history ph ON ph.symbol_id = s.id
                GROUP BY s.id, s.ticker
                ORDER BY s.ticker
            """)
        )
        symbols = result.fetchall()

    for symbol_id, ticker, last_stored in symbols:
        start, end = fetch_window(last_stored, today, full=full)
        print(f"  {ticker:6} {start} -> {end}", end=" ", flush=True)

        bars = provider.get_history(ticker, start, end)
        if not bars:
            print("no data")
            continue

        new = rev = 0
        async with async_session() as session:
            for bar in bars:
                row = (
                    await session.execute(
                        _UPSERT_PRICE,
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
                ).fetchone()
                if row is None:
                    continue  # unchanged — DO UPDATE skipped it
                if row.inserted:
                    new += 1
                else:
                    rev += 1
            await session.commit()

        inserted += new
        revised += rev
        print(f"{len(bars):4} bars  {new:4} new  {rev:4} revised  latest {bars[-1].date}")

    return inserted, revised


async def refresh_macro(provider: FredProvider, *, full: bool) -> tuple[int, int]:
    today = date.today()
    inserted = revised = 0

    async with async_session() as session:
        result = await session.execute(
            text("SELECT series, MAX(date) FROM macro_history GROUP BY series")
        )
        stored = dict(result.fetchall())

    for series_key, series_id in SERIES.items():
        start, end = fetch_window(stored.get(series_key), today, full=full)
        print(f"  {series_key:16} ({series_id:8}) {start} -> {end}", end=" ", flush=True)

        data = provider.get_series_history(series_key, start, end)
        if not data:
            print("no data")
            continue

        new = rev = 0
        async with async_session() as session:
            for point in data:
                row = (
                    await session.execute(
                        _UPSERT_MACRO,
                        {
                            "series": series_key,
                            "date": date.fromisoformat(point["date"]),
                            "value": point["value"],
                        },
                    )
                ).fetchone()
                if row is None:
                    continue
                if row.inserted:
                    new += 1
                else:
                    rev += 1
            await session.commit()

        inserted += new
        revised += rev
        print(f"{len(data):4} points  {new:4} new  {rev:4} revised")

    return inserted, revised


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full",
        action="store_true",
        help="pull the full 5-year window for everything (weekly repair pass)",
    )
    args = parser.parse_args()

    mode = "full restatement" if args.full else "incremental catch-up"
    print(f"Price history ({mode})...")

    # The two halves are independent: a FRED outage must not discard prices
    # that already committed, and either failing has to reach the exit code
    # so systemd marks the run failed instead of it passing silently.
    failed: list[str] = []

    try:
        p_new, p_rev = await refresh_prices(YFinanceProvider(), full=args.full)
        print(f"Prices: {p_new} new, {p_rev} revised\n")
    except Exception as exc:
        failed.append(f"prices: {exc}")
        print(f"Prices: FAILED — {exc}\n")

    print(f"Macro history ({mode})...")
    try:
        m_new, m_rev = await refresh_macro(FredProvider(), full=args.full)
        print(f"Macro: {m_new} new, {m_rev} revised\n")
    except Exception as exc:
        failed.append(f"macro: {exc}")
        print(f"Macro: FAILED — {exc}\n")

    if failed:
        print("FAILED: " + "; ".join(failed))
        return 1

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
