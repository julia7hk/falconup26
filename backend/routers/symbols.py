"""Symbol endpoints — price quotes, history, search."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from market import get_price_fetcher

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


@router.get("/catalog")
async def list_symbols(session: AsyncSession = Depends(get_session)):
    """All symbols in the database with their latest closing price."""
    result = await session.execute(text("""
        SELECT s.ticker, s.name, s.type, s.sector, s.leverage_factor,
               ph.close, ph.date
        FROM symbol s
        LEFT JOIN LATERAL (
            SELECT close, date FROM price_history
            WHERE symbol_id = s.id ORDER BY date DESC LIMIT 1
        ) ph ON true
        ORDER BY s.ticker
    """))
    return [
        {
            "ticker": row.ticker,
            "name": row.name,
            "type": row.type,
            "sector": row.sector,
            "leverage_factor": float(row.leverage_factor),
            "latest_close": float(row.close) if row.close else None,
            "latest_date": row.date.isoformat() if row.date else None,
        }
        for row in result.fetchall()
    ]


@router.get("/{ticker}/history-db")
async def get_history_db(
    ticker: str,
    days: int = Query(default=365, ge=1, le=1825),
    session: AsyncSession = Depends(get_session),
):
    """Daily OHLCV bars from the database."""
    cutoff = date.today() - timedelta(days=days)
    result = await session.execute(
        text("""
            SELECT ph.date, ph.open, ph.high, ph.low, ph.close, ph.volume
            FROM price_history ph
            JOIN symbol s ON s.id = ph.symbol_id
            WHERE s.ticker = :ticker AND ph.date >= :cutoff
            ORDER BY ph.date
        """),
        {"ticker": ticker.upper(), "cutoff": cutoff},
    )
    rows = result.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No DB price data for: {ticker}")
    return [
        {
            "date": row.date.isoformat(),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": row.volume,
        }
        for row in rows
    ]


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
