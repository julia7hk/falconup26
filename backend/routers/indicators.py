"""Indicator endpoints — per-symbol technical indicators + composite signal."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from indicators.composite import composite_score
from indicators.math import (
    atr,
    beta,
    bollinger_width,
    macd,
    rsi,
    sharpe_ratio,
    sma_crossover,
)

router = APIRouter(prefix="/api/symbols", tags=["indicators"])

# SMA crossover needs 200 days + warm-up; fetch extra to be safe
HISTORY_DAYS = 600
MIN_POINTS_BASIC = 35  # enough for MACD (26+9)
MIN_POINTS_SMA = 200


@router.get("/{ticker}/indicators")
async def get_indicators(
    ticker: str,
    session: AsyncSession = Depends(get_session),
):
    """All 7 technical indicators + composite Buy/Hold/Sell signal."""
    ticker = ticker.upper()
    cutoff = date.today() - timedelta(days=HISTORY_DAYS)

    # Fetch symbol + SPY price history joined on date
    result = await session.execute(
        text("""
            SELECT ph.date, ph.close AS symbol_close,
                   ph.high AS symbol_high, ph.low AS symbol_low,
                   spy.close AS spy_close
            FROM price_history ph
            JOIN symbol s ON s.id = ph.symbol_id
            JOIN symbol spy_s ON spy_s.ticker = 'SPY'
            JOIN price_history spy
                ON spy.symbol_id = spy_s.id AND spy.date = ph.date
            WHERE s.ticker = :ticker AND ph.date >= :cutoff
            ORDER BY ph.date
        """),
        {"ticker": ticker, "cutoff": cutoff},
    )
    rows = result.fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No price history for {ticker}",
        )

    closes = [float(r.symbol_close) for r in rows]
    highs = [float(r.symbol_high) for r in rows]
    lows = [float(r.symbol_low) for r in rows]
    spy_closes = [float(r.spy_close) for r in rows]

    # Fetch risk-free rate from macro_history
    rf_result = await session.execute(
        text("""
            SELECT value FROM macro_history
            WHERE series = 'fed_funds_rate'
            ORDER BY date DESC LIMIT 1
        """)
    )
    rf_row = rf_result.fetchone()
    risk_free_rate = float(rf_row.value) if rf_row else 5.0

    # Compute indicators (skip those that need more data than we have)
    indicators: dict[str, object] = {}
    data_points = len(closes)

    if data_points >= MIN_POINTS_BASIC:
        indicators["rsi"] = rsi(closes)
        indicators["macd"] = macd(closes)
        indicators["bollinger"] = bollinger_width(closes)
        indicators["atr"] = atr(highs, lows, closes)
        indicators["beta"] = beta(closes, spy_closes)
        indicators["sharpe"] = sharpe_ratio(closes, risk_free_rate)

    if data_points >= MIN_POINTS_SMA:
        indicators["sma_crossover"] = sma_crossover(closes)

    composite = composite_score(indicators)

    return {
        "ticker": ticker,
        "computed_at": date.today().isoformat(),
        "data_points": data_points,
        "indicators": {k: asdict(v) for k, v in indicators.items()},
        "composite": asdict(composite),
    }
