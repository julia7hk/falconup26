"""Macro data endpoints — FRED economic indicators."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from market.fred import get_fred_provider

router = APIRouter(prefix="/api/macro", tags=["macro"])


@router.get("/snapshot")
def get_macro_snapshot():
    """Current macro indicators: fed funds rate, VIX, treasury yields."""
    provider = get_fred_provider()
    snap = provider.get_snapshot()
    return {
        "fed_funds_rate": snap.fed_funds_rate,
        "vix": snap.vix,
        "treasury_3mo": snap.treasury_3mo,
        "treasury_2y": snap.treasury_2y,
        "treasury_10y": snap.treasury_10y,
        "treasury_30y": snap.treasury_30y,
        "as_of": snap.as_of.isoformat(),
    }


@router.get("/risk-free-rate")
def get_risk_free_rate():
    """Current fed funds rate (used as risk-free rate for Sharpe ratio)."""
    provider = get_fred_provider()
    rate = provider.get_risk_free_rate()
    if rate is None:
        raise HTTPException(status_code=503, detail="Could not fetch risk-free rate from FRED")
    return {"rate": rate, "source": "FRED DFF (Daily Federal Funds Effective Rate)"}


@router.get("/vix")
def get_vix():
    """Current VIX level."""
    provider = get_fred_provider()
    vix = provider.get_vix()
    if vix is None:
        raise HTTPException(status_code=503, detail="Could not fetch VIX from FRED")
    return {"vix": vix, "source": "FRED VIXCLS (CBOE Volatility Index)"}


@router.get("/history/{series}")
def get_series_history(
    series: str,
    days: int = Query(default=365, ge=1, le=3650),
):
    """Historical values for a FRED series (e.g. vix, fed_funds_rate, treasury_10y)."""
    provider = get_fred_provider()
    end = date.today()
    start = end - timedelta(days=days)
    try:
        data = provider.get_series_history(series, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not data:
        raise HTTPException(status_code=404, detail=f"No data for series: {series}")
    return data
