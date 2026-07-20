"""Portfolio risk endpoints — concentration, correlation, stress scenarios, risk grade."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import date, timedelta

import numpy as np
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


async def _fetch_market_data(
    session: AsyncSession,
    user_id: str,
    extra_tickers: list[str] | None = None,
) -> dict:
    """Fetch raw materials for risk analysis — DB queries + live quotes only.

    No derived risk structures (weights, returns, betas) are computed here; that
    is `_build_risk_data`'s job, so a modified holdings list (what-if) can be
    re-derived from the same materials. Returns:
        held: list of holding dicts for the user's current positions
              (ticker, symbol_id, sector, leverage_factor, shares, avg_cost)
        symbol_meta: dict[ticker -> {symbol_id, name, sector, leverage_factor}]
              for held symbols plus any resolvable `extra_tickers` (used when a
              what-if buys a symbol not currently held)
        quote_map: dict[ticker -> live price] for held + extra symbols
        prices_by_ticker: dict[ticker -> {date_str: close}] for held + extra + SPY
    """
    extra_tickers = extra_tickers or []

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

    held = [
        {
            "ticker": row.ticker,
            "symbol_id": row.symbol_id,
            "sector": row.sector,
            "leverage_factor": float(row.leverage_factor),
            "shares": float(row.shares),
            "avg_cost": float(row.avg_cost),
        }
        for row in rows
    ]
    symbol_meta: dict[str, dict] = {
        h["ticker"]: {
            "symbol_id": h["symbol_id"],
            "sector": h["sector"],
            "leverage_factor": h["leverage_factor"],
        }
        for h in held
    }

    # 1b. Resolve any extra tickers not already held (for what-if buys)
    wanted_extra = [t for t in extra_tickers if t not in symbol_meta]
    if wanted_extra:
        extra_result = await session.execute(
            text("""
                SELECT id AS symbol_id, ticker, name, sector, leverage_factor
                FROM symbol WHERE ticker = ANY(:tickers)
            """),
            {"tickers": wanted_extra},
        )
        for row in extra_result.fetchall():
            symbol_meta[row.ticker] = {
                "symbol_id": row.symbol_id,
                "sector": row.sector,
                "leverage_factor": float(row.leverage_factor),
            }

    # 2. Fetch live quotes for market values (held + extra symbols)
    fetcher = get_price_fetcher()
    quote_tickers = list(symbol_meta.keys())

    async def _fetch_quote(ticker: str):
        try:
            return await asyncio.to_thread(fetcher.get_quote, ticker)
        except Exception:
            return None

    quotes = await asyncio.gather(*(_fetch_quote(t) for t in quote_tickers))
    quote_map = {
        t: (q.price if q else None) for t, q in zip(quote_tickers, quotes)
    }

    # 3. Fetch price history for all fetched symbols + SPY, last 5 years
    symbol_ids = [m["symbol_id"] for m in symbol_meta.values()]
    cutoff = date.today() - timedelta(days=365 * 5)

    # Get SPY symbol_id
    spy_result = await session.execute(
        text("SELECT id FROM symbol WHERE ticker = 'SPY'")
    )
    spy_row = spy_result.fetchone()

    all_symbol_ids = list(set(symbol_ids + ([spy_row.id] if spy_row else [])))

    # Fetch all price history in one query
    prices_by_ticker: dict[str, dict[str, float]] = {}
    if all_symbol_ids:
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
        for pr in result.fetchall():
            date_str = pr.date.isoformat() if hasattr(pr.date, "isoformat") else str(pr.date)
            prices_by_ticker.setdefault(pr.ticker, {})[date_str] = float(pr.close)

    return {
        "held": held,
        "symbol_meta": symbol_meta,
        "quote_map": quote_map,
        "prices_by_ticker": prices_by_ticker,
    }


def _build_risk_data(
    holdings_input: list[dict],
    quote_map: dict[str, float | None],
    prices_by_ticker: dict[str, dict[str, float]],
) -> dict:
    """Derive the risk-analysis data dict from a holdings list + raw materials.

    Pure: no DB, no network. `holdings_input` is any list of positions (the
    user's current holdings for `/risk`, or a post-trade copy for `/what-if`) —
    each item needs ticker, sector, leverage_factor, shares, avg_cost. Returns
    the dict consumed by `_compute_risk_metrics` (and by `/correlation`,
    `/stress`). Returns `{"empty": True}` when there are no positions.
    """
    if not holdings_input:
        return {"empty": True}

    tickers = [h["ticker"] for h in holdings_input]

    # Compute market values and weights (fall back to avg_cost if no live quote)
    holdings = []
    market_values = []
    for h in holdings_input:
        price = quote_map.get(h["ticker"])
        if price is None:
            price = h["avg_cost"]
        mv = h["shares"] * price
        market_values.append(mv)
        holdings.append({**h, "price": price, "market_value": mv})

    total_value = sum(market_values)
    weights = (
        [mv / total_value for mv in market_values]
        if total_value > 0
        else [1.0 / len(holdings_input)] * len(holdings_input)
    )

    # Compute per-ticker date sets for flexible alignment
    dates_by_ticker: dict[str, set[str]] = {}
    for t in tickers:
        if t in prices_by_ticker:
            dates_by_ticker[t] = set(prices_by_ticker[t].keys())

    spy_date_set = set(prices_by_ticker["SPY"].keys()) if "SPY" in prices_by_ticker else set()

    # Global intersection (all holdings + SPY) for portfolio-level series
    all_dates: set[str] | None = None
    for t in tickers:
        if t in dates_by_ticker:
            all_dates = dates_by_ticker[t] if all_dates is None else all_dates & dates_by_ticker[t]
    if spy_date_set and all_dates is not None:
        all_dates = all_dates & spy_date_set
    sorted_dates = sorted(all_dates) if all_dates else []

    # Per-pair correlation uses pairwise date intersection (fix #3: ragged histories)
    returns_by_ticker: dict[str, list[float]] = {}
    # For correlation, compute returns on each ticker's own full date range
    for t in tickers:
        if t not in prices_by_ticker:
            continue
        t_dates_sorted = sorted(dates_by_ticker[t])
        if len(t_dates_sorted) < 2:
            continue
        closes = [prices_by_ticker[t][d] for d in t_dates_sorted]
        returns = [(closes[i] - closes[i - 1]) / closes[i - 1]
                   for i in range(1, len(closes)) if closes[i - 1] != 0]
        if returns:
            returns_by_ticker[t] = returns

    # For correlation_matrix, we need aligned returns — build pairwise-aligned
    # returns dict using pairwise date intersections
    corr_returns: dict[str, list[float]] = {}
    if len(dates_by_ticker) >= 2:
        # Use intersection of all tickers that HAVE data (not SPY)
        corr_dates: set[str] | None = None
        for t in tickers:
            if t in dates_by_ticker:
                corr_dates = dates_by_ticker[t] if corr_dates is None else corr_dates & dates_by_ticker[t]
        if corr_dates and len(corr_dates) >= 2:
            corr_sorted = sorted(corr_dates)
            for t in tickers:
                if t not in prices_by_ticker:
                    continue
                closes = [prices_by_ticker[t][d] for d in corr_sorted]
                returns = [(closes[i] - closes[i - 1]) / closes[i - 1]
                           for i in range(1, len(closes)) if closes[i - 1] != 0]
                if returns:
                    corr_returns[t] = returns

    spy_returns = []
    if "SPY" in prices_by_ticker and len(sorted_dates) >= 2:
        spy_closes = [prices_by_ticker["SPY"][d] for d in sorted_dates]
        spy_returns = [(spy_closes[i] - spy_closes[i - 1]) / spy_closes[i - 1]
                       for i in range(1, len(spy_closes)) if spy_closes[i - 1] != 0]

    # 5. Compute per-symbol betas (fix #5: None instead of silent 1.0 fallback)
    betas: list[float | None] = []
    for t in tickers:
        if t in prices_by_ticker and "SPY" in prices_by_ticker:
            # Use pairwise intersection with SPY for this ticker
            pair_dates = sorted(dates_by_ticker.get(t, set()) & spy_date_set)
            if len(pair_dates) >= 60:
                sym_closes = [prices_by_ticker[t][d] for d in pair_dates]
                spy_closes_aligned = [prices_by_ticker["SPY"][d] for d in pair_dates]
                try:
                    beta_result = compute_beta(sym_closes, spy_closes_aligned)
                    betas.append(beta_result.value)
                except Exception:
                    logger.warning("Beta calculation failed for %s, marking unavailable", t)
                    betas.append(None)
            else:
                logger.warning("Beta unavailable for %s: only %d aligned dates (need 60)", t, len(pair_dates))
                betas.append(None)
        else:
            betas.append(None)

    # 6. Compute portfolio value time series using normalized prices (fix #1)
    # Normalize each holding's price to base-1 (price/price_on_first_date)
    # then weight by portfolio weight — this ensures drawdown reflects
    # true weighted returns, not nominal price differences.
    portfolio_values = []
    portfolio_dates = []
    if sorted_dates:
        # Get base prices (first date in aligned series)
        base_prices: dict[str, float] = {}
        for i, t in enumerate(tickers):
            if t in prices_by_ticker and sorted_dates[0] in prices_by_ticker[t]:
                base_prices[t] = prices_by_ticker[t][sorted_dates[0]]

        for d in sorted_dates:
            daily_value = 0.0
            for i, t in enumerate(tickers):
                if t not in base_prices or base_prices[t] == 0:
                    continue
                price = prices_by_ticker[t].get(d, 0)
                # Normalized return from base * weight
                daily_value += weights[i] * (price / base_prices[t])
            if daily_value > 0:
                portfolio_values.append(daily_value)
                portfolio_dates.append(d)

    return {
        "empty": False,
        "holdings": holdings,
        "weights": weights,
        "tickers": tickers,
        "returns_by_ticker": returns_by_ticker,
        "corr_returns": corr_returns,
        "spy_returns": spy_returns,
        "betas": betas,
        "portfolio_value": total_value,
        "portfolio_values": portfolio_values,
        "portfolio_dates": portfolio_dates,
        "prices_by_ticker": prices_by_ticker,
        "data_days": len(sorted_dates),
    }


async def _fetch_portfolio_risk_data(
    session: AsyncSession,
    user_id: str,
) -> dict:
    """Get the risk data for a user's current portfolio, ready to analyze.

    This is a shortcut that runs the two steps back to back:
      1. `_fetch_market_data` — load the user's holdings, live prices, and
         price history from the DB.
      2. `_build_risk_data` — turn all that into the numbers the risk math
         needs (weights, returns, betas, etc.).

    The read-only endpoints (`/risk`, `/correlation`, `/stress`) just want
    "the current portfolio," so they call this and don't have to think about
    the two steps. (What-if calls the two steps itself, because it needs to
    run step 2 twice — once for the real portfolio and once for the pretend
    one after a trade.) Returns `{"empty": True}` if the user owns nothing.
    """
    materials = await _fetch_market_data(session, user_id)
    return _build_risk_data(
        materials["held"],
        materials["quote_map"],
        materials["prices_by_ticker"],
    )


# ---------------------------------------------------------------------------
# Shared risk computation
# ---------------------------------------------------------------------------


# Empty-portfolio risk payload (no holdings to analyze). Endpoints add
# `computed_at` themselves so this stays a pure constant.
_EMPTY_RISK_METRICS = {
    "concentration": None,
    "effective_leverage": None,
    "portfolio_beta": None,
    "max_drawdown": None,
    "risk_grade": None,
    "holdings_count": 0,
    "data_days": 0,
}


def _compute_risk_metrics(data: dict) -> dict:
    """Compute the full risk payload from a fetched data dict.

    Pure computation over the output of `_fetch_portfolio_risk_data` (or a
    modified copy of it, as the what-if endpoint produces) — no DB, no
    network. Shared by `GET /risk` and `POST /what-if` so the two can never
    diverge. Returns the metrics without `computed_at`; callers add that.
    """
    if data["empty"]:
        return dict(_EMPTY_RISK_METRICS)

    conc = concentration(
        data["weights"],
        [h["sector"] for h in data["holdings"]],
    )
    lev = effective_leverage(
        data["weights"],
        [h["leverage_factor"] for h in data["holdings"]],
    )
    # Portfolio beta: exclude holdings with unavailable beta, use available ones
    available_betas = [(w, b) for w, b in zip(data["weights"], data["betas"]) if b is not None]
    if available_betas:
        beta_weights, beta_values = zip(*available_betas)
        # Renormalize weights over holdings with beta data
        total_beta_weight = sum(beta_weights)
        norm_weights = [w / total_beta_weight for w in beta_weights]
        beta_r = portfolio_beta(norm_weights, list(beta_values))
    else:
        beta_r = portfolio_beta([1.0], [1.0])  # no data, assume market

    # Correlation (only if 2+ holdings with aligned return data)
    corr = None
    if len(data["corr_returns"]) >= 2:
        try:
            corr = correlation_matrix(data["corr_returns"])
            # Guard against NaN from zero-variance series
            if corr is not None and (
                not np.isfinite(corr.avg_pairwise)
                or any(not np.isfinite(v) for row in corr.matrix.values() for v in row.values())
            ):
                logger.warning("Correlation matrix contains NaN/Inf, discarding")
                corr = None
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
        "data_days": data["data_days"],
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
    return {
        **_compute_risk_metrics(data),
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

    if len(data["corr_returns"]) < 2:
        return {
            "matrix": {},
            "avg_pairwise": None,
            "max_pair": None,
            "tickers": data["tickers"],
            "data_points": 0,
            "note": "need at least 2 holdings with price history for correlation",
        }

    try:
        corr = correlation_matrix(data["corr_returns"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Correlation failed: {exc}")

    # Guard NaN from zero-variance series
    if not np.isfinite(corr.avg_pairwise):
        raise HTTPException(status_code=500, detail="Correlation produced NaN (zero-variance series)")

    first_ticker = next(iter(data["corr_returns"]))
    data_points = len(data["corr_returns"][first_ticker])

    return {
        "matrix": corr.matrix,
        "avg_pairwise": corr.avg_pairwise,
        "max_pair": list(corr.max_pair),
        "tickers": list(data["corr_returns"].keys()),
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
