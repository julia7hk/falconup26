"""Portfolio risk endpoints — concentration, correlation, stress scenarios, risk grade."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from db import get_session
from indicators.math import beta as compute_beta
from market import get_price_fetcher
from risk.math import (
    STRESS_SCENARIOS,
    concentration,
    correlation_matrix,
    effective_leverage,
    historical_stress_test,
    max_drawdown,
    portfolio_beta,
    risk_grade,
    worst_period,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["risk"])


# ---------------------------------------------------------------------------
# Shared data-fetching helper
# ---------------------------------------------------------------------------


async def _fetch_portfolio_risk_data(
    session: AsyncSession,
    user_id: str,
) -> dict:
    """Fetch everything needed for risk analysis in one pass.

    Returns a dict with:
        holdings: list of dicts (ticker, sector, leverage_factor, shares, avg_cost)
        weights: list of floats (portfolio weight fractions, by market value)
        tickers: list of ticker strings
        returns_by_ticker: dict[ticker -> list[float]] (aligned daily returns)
        spy_returns: list[float] (SPY daily returns, same dates)
        betas: list[float] (per-holding beta vs SPY)
        portfolio_value: float (total market value)
        portfolio_values: list[float] (daily portfolio value series)
        portfolio_dates: list[str] (dates for portfolio_values)
    """
    # 1. Get user's holdings with symbol info
    result = await session.execute(
        text("""
            SELECT ph.id, s.id AS symbol_id, s.ticker, s.name, s.sector,
                   s.leverage_factor, ph.shares, ph.avg_cost
            FROM portfolio_holding ph
            JOIN symbol s ON s.id = ph.symbol_id
            WHERE ph.user_id = :user_id
            ORDER BY s.ticker
        """),
        {"user_id": user_id},
    )
    rows = result.fetchall()

    if not rows:
        return {"empty": True}

    # 2. Fetch live quotes for market values
    fetcher = get_price_fetcher()
    tickers = [row.ticker for row in rows]

    async def _fetch_quote(ticker: str):
        try:
            return await asyncio.to_thread(fetcher.get_quote, ticker)
        except Exception:
            return None

    quotes = await asyncio.gather(*(_fetch_quote(t) for t in tickers))
    quote_map = dict(zip(tickers, quotes))

    # Compute market values and weights
    holdings = []
    market_values = []
    for row in rows:
        quote = quote_map.get(row.ticker)
        price = quote.price if quote else float(row.avg_cost)  # fallback to avg_cost
        mv = float(row.shares) * price
        market_values.append(mv)
        holdings.append({
            "ticker": row.ticker,
            "symbol_id": row.symbol_id,
            "sector": row.sector,
            "leverage_factor": float(row.leverage_factor),
            "shares": float(row.shares),
            "avg_cost": float(row.avg_cost),
            "price": price,
            "market_value": mv,
        })

    total_value = sum(market_values)
    weights = [mv / total_value for mv in market_values] if total_value > 0 else [1.0 / len(rows)] * len(rows)

    # 3. Fetch price history for all holdings + SPY, last 5 years (for drawdown + stress)
    symbol_ids = [row.symbol_id for row in rows]
    cutoff = date.today() - timedelta(days=365 * 5)

    # Get SPY symbol_id
    spy_result = await session.execute(
        text("SELECT id FROM symbol WHERE ticker = 'SPY'")
    )
    spy_row = spy_result.fetchone()

    all_symbol_ids = list(set(symbol_ids + ([spy_row.id] if spy_row else [])))

    # Fetch all price history in one query
    result = await session.execute(
        text("""
            SELECT s.ticker, ph.date, ph.close
            FROM price_history ph
            JOIN symbol s ON s.id = ph.symbol_id
            WHERE ph.symbol_id = ANY(:symbol_ids) AND ph.date >= :cutoff
            ORDER BY ph.date
        """),
        {"symbol_ids": all_symbol_ids, "cutoff": cutoff},
    )
    price_rows = result.fetchall()

    # Organize by ticker -> {date_str: close}
    prices_by_ticker: dict[str, dict[str, float]] = {}
    for pr in price_rows:
        ticker_key = pr.ticker
        date_str = pr.date.isoformat() if hasattr(pr.date, "isoformat") else str(pr.date)
        prices_by_ticker.setdefault(ticker_key, {})[date_str] = float(pr.close)

    # 4. Align daily returns by date (only dates present for ALL holdings + SPY)
    all_dates = None
    for t in tickers:
        if t in prices_by_ticker:
            t_dates = set(prices_by_ticker[t].keys())
            all_dates = t_dates if all_dates is None else all_dates & t_dates

    if spy_row and "SPY" in prices_by_ticker:
        spy_dates = set(prices_by_ticker["SPY"].keys())
        if all_dates is not None:
            all_dates = all_dates & spy_dates

    sorted_dates = sorted(all_dates) if all_dates else []

    # Compute daily returns for each ticker
    returns_by_ticker: dict[str, list[float]] = {}
    for t in tickers:
        if t not in prices_by_ticker or len(sorted_dates) < 2:
            continue
        closes = [prices_by_ticker[t][d] for d in sorted_dates]
        returns = [(closes[i] - closes[i - 1]) / closes[i - 1]
                   for i in range(1, len(closes)) if closes[i - 1] != 0]
        if returns:
            returns_by_ticker[t] = returns

    spy_returns = []
    if "SPY" in prices_by_ticker and len(sorted_dates) >= 2:
        spy_closes = [prices_by_ticker["SPY"][d] for d in sorted_dates]
        spy_returns = [(spy_closes[i] - spy_closes[i - 1]) / spy_closes[i - 1]
                       for i in range(1, len(spy_closes)) if spy_closes[i - 1] != 0]

    # 5. Compute per-symbol betas
    betas = []
    for t in tickers:
        if t in prices_by_ticker and "SPY" in prices_by_ticker and len(sorted_dates) >= 60:
            sym_closes = [prices_by_ticker[t][d] for d in sorted_dates]
            spy_closes = [prices_by_ticker["SPY"][d] for d in sorted_dates]
            try:
                beta_result = compute_beta(sym_closes, spy_closes)
                betas.append(beta_result.value)
            except Exception:
                betas.append(1.0)  # fallback
        else:
            betas.append(1.0)

    # 6. Compute portfolio value time series (for drawdown)
    portfolio_values = []
    portfolio_dates = []
    if sorted_dates:
        for d in sorted_dates:
            daily_value = sum(
                weights[i] * prices_by_ticker[tickers[i]].get(d, 0)
                for i in range(len(tickers))
                if tickers[i] in prices_by_ticker
            )
            if daily_value > 0:
                portfolio_values.append(daily_value)
                portfolio_dates.append(d)

    return {
        "empty": False,
        "holdings": holdings,
        "weights": weights,
        "tickers": tickers,
        "returns_by_ticker": returns_by_ticker,
        "spy_returns": spy_returns,
        "betas": betas,
        "portfolio_value": total_value,
        "portfolio_values": portfolio_values,
        "portfolio_dates": portfolio_dates,
        "prices_by_ticker": prices_by_ticker,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/risk")
async def get_portfolio_risk(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Portfolio risk analysis: concentration, leverage, beta, drawdown, grade."""
    data = await _fetch_portfolio_risk_data(session, user["id"])

    if data["empty"]:
        return {
            "concentration": None,
            "effective_leverage": None,
            "portfolio_beta": None,
            "max_drawdown": None,
            "risk_grade": None,
            "holdings_count": 0,
            "computed_at": date.today().isoformat(),
        }

    conc = concentration(
        data["weights"],
        [h["sector"] for h in data["holdings"]],
    )
    lev = effective_leverage(
        data["weights"],
        [h["leverage_factor"] for h in data["holdings"]],
    )
    beta_r = portfolio_beta(data["weights"], data["betas"])

    # Correlation (only if 2+ holdings with return data)
    corr = None
    if len(data["returns_by_ticker"]) >= 2:
        try:
            corr = correlation_matrix(data["returns_by_ticker"])
        except Exception as exc:
            logger.warning("Correlation calculation failed: %s", exc)

    # Max drawdown (only if we have enough portfolio value history)
    dd = None
    if len(data["portfolio_values"]) >= 60:
        try:
            dd = max_drawdown(data["portfolio_values"], data["portfolio_dates"])
        except Exception as exc:
            logger.warning("Max drawdown calculation failed: %s", exc)

    # Risk grade (needs drawdown; use a safe default if unavailable)
    grade = None
    if dd is not None:
        try:
            grade = risk_grade(conc, corr, lev, beta_r, dd)
        except Exception as exc:
            logger.warning("Risk grade calculation failed: %s", exc)

    return {
        "concentration": asdict(conc),
        "effective_leverage": asdict(lev),
        "portfolio_beta": asdict(beta_r),
        "max_drawdown": asdict(dd) if dd else None,
        "risk_grade": asdict(grade) if grade else None,
        "holdings_count": len(data["holdings"]),
        "computed_at": date.today().isoformat(),
    }


@router.get("/correlation")
async def get_portfolio_correlation(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Pairwise correlation matrix of portfolio holdings."""
    data = await _fetch_portfolio_risk_data(session, user["id"])

    if data["empty"]:
        return {
            "matrix": {},
            "avg_pairwise": None,
            "max_pair": None,
            "tickers": [],
            "data_points": 0,
        }

    if len(data["returns_by_ticker"]) < 2:
        return {
            "matrix": {},
            "avg_pairwise": None,
            "max_pair": None,
            "tickers": data["tickers"],
            "data_points": 0,
            "note": "need at least 2 holdings with price history for correlation",
        }

    try:
        corr = correlation_matrix(data["returns_by_ticker"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Correlation failed: {exc}")

    # Data points = length of return series (all same after alignment)
    first_ticker = next(iter(data["returns_by_ticker"]))
    data_points = len(data["returns_by_ticker"][first_ticker])

    return {
        "matrix": corr.matrix,
        "avg_pairwise": corr.avg_pairwise,
        "max_pair": list(corr.max_pair),
        "tickers": list(data["returns_by_ticker"].keys()),
        "data_points": data_points,
        "signal": corr.signal,
    }


@router.get("/stress")
async def get_stress_test(
    scenario: str = "all",
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Stress test: replay historical market events on current portfolio."""
    data = await _fetch_portfolio_risk_data(session, user["id"])

    if data["empty"]:
        return {"scenarios": [], "holdings_count": 0}

    prices_by_ticker = data["prices_by_ticker"]
    tickers = data["tickers"]
    weights = data["weights"]
    portfolio_value = data["portfolio_value"]

    # Determine which scenarios to run
    if scenario == "all":
        scenarios_to_run = STRESS_SCENARIOS
    elif scenario in STRESS_SCENARIOS:
        scenarios_to_run = {scenario: STRESS_SCENARIOS[scenario]}
    else:
        valid = list(STRESS_SCENARIOS.keys()) + ["all"]
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario '{scenario}'. Valid: {valid}",
        )

    results = []
    for key, sc in scenarios_to_run.items():
        # Extract prices for each holding in the scenario date range
        holdings_prices: dict[str, dict[str, float]] = {}
        for t in tickers:
            if t not in prices_by_ticker:
                continue
            filtered = {
                d: p for d, p in prices_by_ticker[t].items()
                if sc["start"] <= d <= sc["end"]
            }
            if filtered:
                holdings_prices[t] = filtered

        try:
            result = historical_stress_test(
                holdings_prices=holdings_prices,
                weights=weights,
                tickers=tickers,
                start_date=sc["start"],
                end_date=sc["end"],
                scenario_name=sc["name"],
                portfolio_value=portfolio_value,
            )
            results.append(asdict(result))
        except Exception as exc:
            logger.warning("Stress test %s failed: %s", key, exc)

    # Add worst 30-day period if we have enough data
    if len(data["portfolio_values"]) > 31:
        try:
            wp = worst_period(
                data["portfolio_values"],
                data["portfolio_dates"],
                window_days=30,
            )
            results.append(asdict(wp))
        except Exception as exc:
            logger.warning("Worst period calculation failed: %s", exc)

    return {
        "scenarios": results,
        "holdings_count": len(data["holdings"]),
        "portfolio_value": round(portfolio_value, 2),
        "disclaimer": "Based on historical data. Past performance does not predict future results.",
    }
