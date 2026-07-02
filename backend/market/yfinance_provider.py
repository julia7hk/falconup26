"""yfinance implementation of DataProvider."""

from __future__ import annotations

from datetime import date, datetime, timezone

import yfinance as yf

from market.models import OHLCV, Quote


class YFinanceProvider:
    """Market data backed by the yfinance library (Yahoo Finance)."""

    def get_quote(self, symbol: str) -> Quote:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = info.last_price
        prev_close = info.previous_close
        change = price - prev_close
        change_pct = (change / prev_close) * 100 if prev_close else 0.0
        return Quote(
            symbol=symbol.upper(),
            price=round(price, 2),
            change=round(change, 2),
            change_percent=round(change_pct, 2),
            timestamp=datetime.now(timezone.utc),
        )

    def get_history(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> list[OHLCV]:
        ticker = yf.Ticker(symbol)
        # yfinance end date is exclusive, so add one day
        df = ticker.history(start=start.isoformat(), end=end.isoformat(), auto_adjust=True)
        if df.empty:
            return []
        bars: list[OHLCV] = []
        for ts, row in df.iterrows():
            bars.append(
                OHLCV(
                    date=ts.date(),
                    open=round(float(row["Open"]), 2),
                    high=round(float(row["High"]), 2),
                    low=round(float(row["Low"]), 2),
                    close=round(float(row["Close"]), 2),
                    volume=int(row["Volume"]),
                )
            )
        return bars

    def search_symbols(self, query: str) -> list[dict]:
        results = yf.search(query, max_results=10)
        if not results or "quotes" not in results:
            return []
        return [
            {
                "symbol": q.get("symbol", ""),
                "name": q.get("shortname") or q.get("longname", ""),
                "type": q.get("quoteType", ""),
                "exchange": q.get("exchange", ""),
            }
            for q in results["quotes"]
        ]
