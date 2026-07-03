"""Symbol endpoints — price quotes, history, search."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from market import get_price_fetcher

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


@router.get("/search")
def search_symbols(q: str = Query(min_length=1, max_length=20)):
    """Autocomplete symbol search."""
    fetcher = get_price_fetcher()
    return fetcher.search_symbols(q)


@router.get("/{ticker}/quote")
def get_quote(ticker: str):
    """Current price snapshot for a symbol."""
    fetcher = get_price_fetcher()
    try:
        quote = fetcher.get_quote(ticker)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {ticker}") from exc
    return {
        "symbol": quote.symbol,
        "price": quote.price,
        "change": quote.change,
        "change_percent": quote.change_percent,
        "timestamp": quote.timestamp.isoformat(),
    }


@router.get("/{ticker}/history")
def get_history(
    ticker: str,
    days: int = Query(default=365, ge=1, le=1825),
):
    """Daily OHLCV bars. Default 1 year, max 5 years."""
    fetcher = get_price_fetcher()
    end = date.today()
    start = end - timedelta(days=days)
    bars = fetcher.get_history(ticker, start, end)
    if not bars:
        raise HTTPException(status_code=404, detail=f"No price data for: {ticker}")
    return [
        {
            "date": bar.date.isoformat(),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        for bar in bars
    ]


@router.get("/{ticker}/sector")
def get_sector_info(ticker: str):
    """Sector/industry classification for a symbol."""
    fetcher = get_price_fetcher()
    try:
        info = fetcher.get_sector_info(ticker)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {ticker}") from exc
    return {
        "symbol": info.symbol,
        "sector": info.sector,
        "industry": info.industry,
        "is_etf": info.is_etf,
    }
