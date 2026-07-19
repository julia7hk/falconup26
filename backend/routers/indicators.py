"""Indicator endpoints — per-symbol technical indicators + composite signal."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from db import get_session
from indicators.composite import composite_score
from indicators.math import (
    atr,
    beta,
    bollinger_width,
    macd,
    max_drawdown,
    rsi,
    sharpe_ratio,
    sma_crossover,
    sortino_ratio,
)

router = APIRouter(prefix="/api/symbols", tags=["indicators"])

# SMA crossover needs 200 days + warm-up; fetch extra to be safe
HISTORY_DAYS = 600

# Per-indicator minimum data requirements
MIN_POINTS = {
    "rsi": 15,          # period (14) + 1
    "macd": 35,         # slow (26) + signal (9)
    "bollinger": 20,    # period
    "atr": 15,          # period (14) + 1
    "beta": 60,         # ~3 months for meaningful covariance
    "sharpe": 60,       # ~3 months for meaningful Sharpe
    "sortino": 60,      # ~3 months for meaningful Sortino
    "max_drawdown": 30, # ~6 weeks for a meaningful peak-to-trough
    "sma_crossover": 200,
}


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
    dates = [
        r.date.isoformat() if hasattr(r.date, "isoformat") else str(r.date)
        for r in rows
    ]

    # Fetch risk-free rate from macro_history
    rf_result = await session.execute(
        text("""
            SELECT value FROM macro_history
            WHERE series = 'fed_funds_rate'
            ORDER BY date DESC LIMIT 1
        """)
    )
    rf_row = rf_result.fetchone()
    if rf_row:
        risk_free_rate = float(rf_row.value)
        risk_free_rate_source = "FRED DFF"
    else:
        risk_free_rate = 5.0
        risk_free_rate_source = "default (macro_history empty)"
        logger.warning("No fed_funds_rate in macro_history, using default 5.0%%")

    # Compute each indicator independently — skip if insufficient data,
    # isolate errors so one failure doesn't take down the whole endpoint.
    indicators: dict[str, object] = {}
    errors: list[str] = []
    data_points = len(closes)

    indicator_fns = {
        "rsi": lambda: rsi(closes),
        "macd": lambda: macd(closes),
        "bollinger": lambda: bollinger_width(closes),
        "atr": lambda: atr(highs, lows, closes),
        "beta": lambda: beta(closes, spy_closes),
        "sharpe": lambda: sharpe_ratio(closes, risk_free_rate),
        "sortino": lambda: sortino_ratio(closes, risk_free_rate),
        "max_drawdown": lambda: max_drawdown(closes, dates),
        "sma_crossover": lambda: sma_crossover(closes),
    }

    for name, fn in indicator_fns.items():
        if data_points < MIN_POINTS[name]:
            continue
        try:
            indicators[name] = fn()
        except Exception as exc:
            logger.warning("Indicator %s failed for %s: %s", name, ticker, exc)
            errors.append(name)

    composite = composite_score(indicators)

    response = {
        "ticker": ticker,
        "computed_at": date.today().isoformat(),
        "data_points": data_points,
        "risk_free_rate_source": risk_free_rate_source,
        "indicators": {k: asdict(v) for k, v in indicators.items()},
        "composite": asdict(composite),
    }
    if errors:
        response["failed_indicators"] = errors
    return response
