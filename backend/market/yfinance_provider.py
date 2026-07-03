"""yfinance implementation of DataProvider."""

from __future__ import annotations

from datetime import date, datetime, timezone

import yfinance as yf

from market.models import OHLCV, Quote, SectorInfo

# Hardcoded ETF categories for concentration analysis.
# yfinance doesn't return sector/industry for ETFs, so we tag them manually.
_ETF_CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "QQQ":   ("Technology",   "Broad Market Tech ETF"),
    "TQQQ":  ("Technology",   "Leveraged Tech ETF"),
    "SQQQ":  ("Technology",   "Inverse Leveraged Tech ETF"),
    "SOXL":  ("Technology",   "Leveraged Semiconductor ETF"),
    "SOXX":  ("Technology",   "Semiconductor ETF"),
    "XLK":   ("Technology",   "Technology Sector ETF"),
    "ARKK":  ("Technology",   "Innovation ETF"),
    "SPY":   ("Broad Market", "S&P 500 ETF"),
    "VOO":   ("Broad Market", "S&P 500 ETF"),
    "VTI":   ("Broad Market", "Total US Market ETF"),
    "IWM":   ("Broad Market", "Small-Cap ETF"),
    "DIA":   ("Broad Market", "Dow Jones ETF"),
    "XLF":   ("Financials",   "Financial Sector ETF"),
    "XLE":   ("Energy",       "Energy Sector ETF"),
    "GLD":   ("Commodities",  "Gold ETF"),
    "TLT":   ("Fixed Income", "Long-Term Treasury ETF"),
    "BND":   ("Fixed Income", "Total Bond ETF"),
}


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
        search = yf.Search(query, max_results=10)
        if not search.quotes:
            return []
        return [
            {
                "symbol": q.get("symbol", ""),
                "name": q.get("shortname") or q.get("longname", ""),
                "type": q.get("quoteType", ""),
                "exchange": q.get("exchange", ""),
            }
            for q in search.quotes
        ]

    def get_sector_info(self, symbol: str) -> SectorInfo:
        symbol = symbol.upper()
        # Fast path: known ETFs
        if symbol in _ETF_CATEGORY_MAP:
            sector, industry = _ETF_CATEGORY_MAP[symbol]
            return SectorInfo(symbol=symbol, sector=sector, industry=industry, is_etf=True)
        # Individual stock: ask yfinance
        ticker = yf.Ticker(symbol)
        info = ticker.info
        sector = info.get("sector", "Unknown")
        industry = info.get("industry", "Unknown")
        is_etf = sector == "Unknown"
        return SectorInfo(symbol=symbol, sector=sector, industry=industry, is_etf=is_etf)
