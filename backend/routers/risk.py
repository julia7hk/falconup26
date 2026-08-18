"""Portfolio risk endpoints — concentration, correlation, stress scenarios, risk grade."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import date, timedelta

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal

from auth import get_current_user
from db import get_session
from indicators.math import beta as compute_beta
from llm_explainer import explain as explain_grade_enriched
from llm_explainer.templates import explain_grade
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


# ---------- request bodies ----------


class WhatIfRequest(BaseModel):
    """A hypothetical trade to simulate against the user's current portfolio."""

    ticker: str = Field(min_length=1, max_length=10)
    action: Literal["buy", "sell"]
    quantity: float = Field(gt=0)


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
        "corr_returns": corr_returns,
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


# Drawdown/grade comparability threshold (what-if). The portfolio value series
# spans the date-intersection of its holdings, so buying a shorter-history symbol
# shrinks the "after" window. If the after window drops below this fraction of the
# before window, the two drawdowns cover different periods and can't be compared.
_MIN_COMPARABLE_WINDOW = 0.9


# Which scalar inside each metric payload to diff, and whether a *lower* value
# is an improvement (less risk). Risk grade is the exception: a higher score is
# safer. Anything not listed here isn't compared (it's descriptive, not scored).
_DIFF_METRICS = [
    ("concentration", "herfindahl_index", True),
    ("effective_leverage", "value", True),
    ("portfolio_beta", "value", True),
    ("max_drawdown", "value", True),
    ("risk_grade", "score", False),
]


def _diff_risk_metrics(before: dict, after: dict) -> dict:
    """Compare two risk payloads metric-by-metric.

    For each scored metric, report the before/after value, the change, and a
    plain direction flag: "improved", "worsened", "unchanged", or "unavailable"
    (when the metric couldn't be computed on either side — e.g. correlation with
    <2 holdings). "improved" means less risk, so for most metrics that's a lower
    number, but for the risk grade it's a higher score.
    """
    diff: dict[str, dict] = {}
    for metric, field, lower_is_better in _DIFF_METRICS:
        b_obj, a_obj = before.get(metric), after.get(metric)
        b = b_obj.get(field) if b_obj else None
        a = a_obj.get(field) if a_obj else None

        if b is None or a is None:
            direction = "unavailable"
            delta = None
        else:
            delta = a - b
            if abs(delta) < 1e-9:
                direction = "unchanged"
            else:
                improved = delta < 0 if lower_is_better else delta > 0
                direction = "improved" if improved else "worsened"

        entry = {"before": b, "after": a, "delta": delta, "direction": direction}
        # Surface the letter grade too — it's what the user actually reads.
        if metric == "risk_grade":
            entry["before_grade"] = b_obj.get("grade") if b_obj else None
            entry["after_grade"] = a_obj.get("grade") if a_obj else None
        diff[metric] = entry
    return diff


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/risk")
async def get_portfolio_risk(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Portfolio risk analysis: concentration, leverage, beta, drawdown, grade.

    Carries the deterministic grade explanation inline (`risk_grade_explanation`)
    so the dashboard renders the "Why this grade?" surface from the payload it
    already fetched, without a second full risk pass. `explain_grade` is a pure
    function of the `risk_grade` object, so this is ~free; the standalone
    `/risk/explain` endpoint stays for the PR2 LLM path.
    """
    data = await _fetch_portfolio_risk_data(session, user["id"])
    metrics = _compute_risk_metrics(data)
    return {
        **metrics,
        "risk_grade_explanation": (
            explain_grade(metrics["risk_grade"]) if metrics["risk_grade"] else None
        ),
        "computed_at": date.today().isoformat(),
    }


@router.get("/risk/explain")
async def explain_portfolio_risk(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Plain-English explanation of the portfolio risk grade.

    LLM-enriched when `GROQ_API_KEY` is set and the rephrasing passes the
    traceability validator; otherwise the deterministic PR1 text (M8 PR2). The
    response `explanation.source` reports which path served it. Either way the
    text is built from the same `_compute_risk_metrics` payload `/risk` returns,
    so it can never describe a different grade than the card shows. When the
    grade can't be computed (no holdings, or under 60 days of aligned history)
    the payload reports `available: false` with a message instead of prose.

    The LLM call is blocking, so it runs in a worker thread to keep the event
    loop free. `/risk` still carries the deterministic explanation inline, so the
    dashboard renders instantly; this endpoint is the (lazily-fetched) enriched
    surface.
    """
    data = await _fetch_portfolio_risk_data(session, user["id"])
    metrics = _compute_risk_metrics(data)
    grade = metrics["risk_grade"]

    if grade is None:
        if metrics["holdings_count"] == 0:
            message = "Add holdings to your portfolio to see a risk explanation."
        else:
            message = (
                "A risk grade needs at least 60 days of overlapping price "
                "history across your holdings. Once there's enough data, an "
                "explanation will appear here."
            )
        return {
            "available": False,
            "message": message,
            "explanation": None,
            "computed_at": date.today().isoformat(),
        }

    explanation = await asyncio.to_thread(explain_grade_enriched, grade)
    return {
        "available": True,
        "message": None,
        "explanation": explanation,
        "computed_at": date.today().isoformat(),
    }


@router.get("/value-history")
async def get_portfolio_value_history(
    days: int = 365,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Dollar value of the current holdings over time (for the value chart).

    Reconstructs what today's basket would have been worth on each past trading
    day: for every date, `sum(shares * close)` across holdings. Uses the daily
    closes already in `price_history` (via `_fetch_market_data`) — no new data.

    Caveat: there's no transaction/lot history, so this replays the *current*
    share counts backward. It shows how the current portfolio's market value
    tracked, not a true account balance that accounts for when each lot was
    bought. `total_cost` is the flat cost basis (sum of `shares * avg_cost`) so
    the frontend can draw a break-even line and read P&L as value − cost.

    `days` caps how far back to go (default 365, max 1825 ≈ 5y of backfill).
    Dates are the intersection where *every* priced holding has a close, so the
    total is always a like-for-like sum. `complete` is false when a holding has
    no price history and was left out of the sum.
    """
    days = max(1, min(days, 365 * 5))
    materials = await _fetch_market_data(session, user["id"])
    held = materials["held"]
    prices_by_ticker = materials["prices_by_ticker"]

    if not held:
        return {
            "series": [],
            "total_cost": 0.0,
            "holdings_count": 0,
            "complete": True,
        }

    total_cost = sum(h["shares"] * h["avg_cost"] for h in held)

    # Holdings that actually have price history (SPY is present for risk math
    # but isn't a holding, so it's naturally excluded — we only iterate `held`).
    priced = [h for h in held if h["ticker"] in prices_by_ticker]
    complete = len(priced) == len(held)

    # Intersection of dates where every priced holding has a close, so each
    # summed point covers the same trading day for the whole basket.
    common_dates: set[str] | None = None
    for h in priced:
        ticker_dates = set(prices_by_ticker[h["ticker"]].keys())
        common_dates = ticker_dates if common_dates is None else common_dates & ticker_dates

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    sorted_dates = sorted(d for d in (common_dates or set()) if d >= cutoff)

    series = []
    for d in sorted_dates:
        value = sum(h["shares"] * prices_by_ticker[h["ticker"]][d] for h in priced)
        series.append({"date": d, "value": round(value, 2)})

    return {
        "series": series,
        "total_cost": round(total_cost, 2),
        "holdings_count": len(held),
        "complete": complete,
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


@router.post("/what-if")
async def what_if(
    body: WhatIfRequest,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Simulate a buy/sell trade and return the before/after risk diff.

    Never modifies the real portfolio. Fetches raw materials once (including the
    target symbol's history in case it isn't held), computes risk for the current
    portfolio ("before"), applies the trade to a copy ("after"), and diffs them.
    """
    ticker = body.ticker.upper()
    materials = await _fetch_market_data(session, user["id"], extra_tickers=[ticker])

    # The symbol must exist in our catalog (held or resolvable as an extra).
    if ticker not in materials["symbol_meta"]:
        raise HTTPException(status_code=404, detail=f"Symbol not in database: {ticker}")

    quote_map = materials["quote_map"]
    prices_by_ticker = materials["prices_by_ticker"]
    held = materials["held"]

    # "Before" = current portfolio.
    before_data = _build_risk_data(held, quote_map, prices_by_ticker)

    # "After" = a copy of the holdings with the trade applied.
    after_holdings = [dict(h) for h in held]
    existing = next((h for h in after_holdings if h["ticker"] == ticker), None)

    if body.action == "buy":
        if existing:
            existing["shares"] += body.quantity
        else:
            # New position. Price it at the live quote, falling back to the most
            # recent close if the quote is unavailable.
            price = quote_map.get(ticker)
            if price is None and prices_by_ticker.get(ticker):
                price = prices_by_ticker[ticker][max(prices_by_ticker[ticker])]
            if price is None:
                raise HTTPException(
                    status_code=400, detail=f"No price data available for {ticker}"
                )
            meta = materials["symbol_meta"][ticker]
            after_holdings.append({
                "ticker": ticker,
                "symbol_id": meta["symbol_id"],
                "sector": meta["sector"],
                "leverage_factor": meta["leverage_factor"],
                "shares": body.quantity,
                "avg_cost": price,
            })
    else:  # sell
        if not existing:
            raise HTTPException(
                status_code=400, detail=f"You don't own {ticker}, nothing to sell"
            )
        if body.quantity > existing["shares"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot sell {body.quantity} shares of {ticker}; you own {existing['shares']}",
            )
        if body.quantity == existing["shares"]:
            after_holdings = [h for h in after_holdings if h["ticker"] != ticker]
        else:
            existing["shares"] -= body.quantity

    after_data = _build_risk_data(after_holdings, quote_map, prices_by_ticker)

    before_metrics = _compute_risk_metrics(before_data)
    after_metrics = _compute_risk_metrics(after_data)

    # Drawdown-window comparability (code-review #1): buying a shorter-history
    # symbol shrinks the "after" date window, so its drawdown would be measured
    # over a shorter period than "before" — a newer symbol then looks safer only
    # because its window excludes older crashes. When the window shrinks
    # materially, null the after drawdown and grade so the diff reports them as
    # not-comparable instead of a misleading improvement. Concentration,
    # leverage, and beta are unaffected and stay comparable.
    notes: list[str] = []
    before_days = before_metrics["data_days"]
    after_days = after_metrics["data_days"]
    if (
        before_metrics["max_drawdown"] is not None
        and before_days > 0
        and after_days < before_days * _MIN_COMPARABLE_WINDOW
    ):
        after_metrics["max_drawdown"] = None
        after_metrics["risk_grade"] = None
        notes.append(
            f"Drawdown and grade can't be compared for this trade: {ticker} has a "
            f"shorter price history ({after_days} vs {before_days} overlapping days), "
            "so the simulated window excludes older market crashes. Concentration, "
            "leverage, and beta remain comparable."
        )

    return {
        "trade": {
            "ticker": ticker,
            "action": body.action,
            "quantity": body.quantity,
        },
        "before": before_metrics,
        "after": after_metrics,
        "diff": _diff_risk_metrics(before_metrics, after_metrics),
        "notes": notes,
        "computed_at": date.today().isoformat(),
        "disclaimer": (
            "Simulation only — your portfolio is unchanged. Educational analysis, "
            "not financial advice."
        ),
    }
