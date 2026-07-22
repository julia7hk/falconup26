"""Pure portfolio risk computation functions.

Every function takes plain Python types (lists, dicts, floats) and returns a
result dataclass.  No database, no network, no side effects.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from risk.models import (
    ConcentrationResult,
    CorrelationResult,
    EffectiveLeverageResult,
    MaxDrawdownResult,
    PortfolioBetaResult,
    RiskGradeResult,
    StressScenarioResult,
)


# ---------------------------------------------------------------------------
# Historical stress scenario date ranges
# ---------------------------------------------------------------------------
#
# Curated real historical events, loaded from stress_scenarios.json (data, not
# math — keeps this module's functions pure). Dates are immutable facts (a crash
# bottom doesn't move), so a static file is a fine home. Longer term we want
# these detected automatically from price history rather than hand-researched —
# see docs/milestones.md "Automatic stress scenario detection".

_SCENARIOS_PATH = Path(__file__).with_name("stress_scenarios.json")

STRESS_SCENARIOS: dict[str, dict] = json.loads(_SCENARIOS_PATH.read_text())


# ---------------------------------------------------------------------------
# Risk functions
# ---------------------------------------------------------------------------


def concentration(
    weights: list[float],
    sectors: list[str],
) -> ConcentrationResult:
    """Concentration score via Herfindahl index + sector breakdown.

    ``weights`` are portfolio weight fractions (must sum to ~1.0).
    ``sectors`` are the sector labels for each holding, same order as weights.
    """
    if len(weights) != len(sectors):
        raise ValueError("weights and sectors must be the same length")
    if not weights:
        raise ValueError("Need at least one holding")

    hhi = sum(w * w for w in weights)

    top_holding_pct = max(weights) * 100

    sector_breakdown: dict[str, float] = {}
    for w, s in zip(weights, sectors):
        sector_breakdown[s] = sector_breakdown.get(s, 0.0) + w * 100
    # Round for display
    sector_breakdown = {k: round(v, 1) for k, v in sector_breakdown.items()}

    if hhi > 0.25:
        signal = "highly_concentrated"
    elif hhi > 0.15:
        signal = "moderate"
    else:
        signal = "diversified"

    return ConcentrationResult(
        herfindahl_index=round(hhi, 4),
        top_holding_pct=round(top_holding_pct, 1),
        sector_breakdown=sector_breakdown,
        signal=signal,
    )


def correlation_matrix(
    returns_by_ticker: dict[str, list[float]],
) -> CorrelationResult:
    """Pairwise correlation matrix from daily returns.

    ``returns_by_ticker`` maps ticker -> list of daily returns, all same length
    and aligned by date.
    """
    tickers = list(returns_by_ticker.keys())
    if len(tickers) < 2:
        raise ValueError("Need at least 2 tickers for correlation")

    n = len(tickers)
    data = np.array([returns_by_ticker[t] for t in tickers])
    corr = np.corrcoef(data)

    # Build nested dict
    matrix: dict[str, dict[str, float]] = {}
    for i, t1 in enumerate(tickers):
        matrix[t1] = {}
        for j, t2 in enumerate(tickers):
            matrix[t1][t2] = round(float(corr[i, j]), 4)

    # Average pairwise (upper triangle, excluding diagonal)
    pairwise = []
    max_corr = -2.0
    max_pair = (tickers[0], tickers[1], 0.0)
    for i in range(n):
        for j in range(i + 1, n):
            c = float(corr[i, j])
            pairwise.append(c)
            if c > max_corr:
                max_corr = c
                max_pair = (tickers[i], tickers[j], round(c, 4))

    avg_pairwise = sum(pairwise) / len(pairwise) if pairwise else 0.0

    if avg_pairwise > 0.8:
        signal = "highly_correlated"
    elif avg_pairwise > 0.5:
        signal = "moderate"
    else:
        signal = "diversified"

    return CorrelationResult(
        matrix=matrix,
        avg_pairwise=round(avg_pairwise, 4),
        max_pair=max_pair,
        signal=signal,
    )


def effective_leverage(
    weights: list[float],
    leverage_factors: list[float],
) -> EffectiveLeverageResult:
    """Weighted average leverage factor across portfolio.

    ``weights`` are portfolio weight fractions (sum to ~1.0).
    ``leverage_factors`` are per-holding leverage factors (e.g. 1, 3, -3).
    """
    if len(weights) != len(leverage_factors):
        raise ValueError("weights and leverage_factors must be the same length")
    if not weights:
        raise ValueError("Need at least one holding")

    # abs() intentional: inverse ETFs (e.g. SQQQ at -3x) carry the same
    # magnitude of leverage risk as bull ETFs, even though they reduce net
    # directional exposure.  We measure leverage as amplification, not direction.
    value = sum(w * abs(lf) for w, lf in zip(weights, leverage_factors))
    leveraged_pct = sum(w for w, lf in zip(weights, leverage_factors) if abs(lf) > 1) * 100

    if value >= 2.5:
        signal = "extreme"
    elif value >= 1.5:
        signal = "high"
    elif value > 1.0:
        signal = "moderate"
    else:
        signal = "none"

    return EffectiveLeverageResult(
        value=round(value, 2),
        leveraged_pct=round(leveraged_pct, 1),
        signal=signal,
    )


def portfolio_beta(
    weights: list[float],
    betas: list[float],
) -> PortfolioBetaResult:
    """Weighted portfolio beta vs S&P 500."""
    if len(weights) != len(betas):
        raise ValueError("weights and betas must be the same length")
    if not weights:
        raise ValueError("Need at least one holding")

    value = sum(w * b for w, b in zip(weights, betas))

    if value < 0.8:
        interpretation = "less volatile than market"
    elif value <= 1.2:
        interpretation = "moves with market"
    elif value <= 2.0:
        interpretation = "more volatile than market"
    else:
        interpretation = "significantly more volatile than market"

    return PortfolioBetaResult(
        value=round(value, 2),
        interpretation=interpretation,
    )


def max_drawdown(
    portfolio_values: list[float],
    dates: list[str],
) -> MaxDrawdownResult:
    """Actual historical max drawdown from a portfolio value time series.

    Scans for the worst peak-to-trough decline.  Also computes annualized
    volatility from daily returns.

    ``portfolio_values`` and ``dates`` must be the same length and in
    chronological order.
    """
    if len(portfolio_values) != len(dates):
        raise ValueError("portfolio_values and dates must be the same length")
    if len(portfolio_values) < 2:
        raise ValueError("Need at least 2 data points")

    values = np.array(portfolio_values)
    daily_returns = np.diff(values) / values[:-1]
    annualized_vol = float(np.std(daily_returns, ddof=1) * np.sqrt(252)) * 100

    # Find max drawdown: worst peak-to-trough decline
    running_max = values[0]
    worst_dd = 0.0
    worst_peak_idx = 0
    worst_trough_idx = 0
    current_peak_idx = 0

    for i in range(1, len(values)):
        if values[i] > running_max:
            running_max = values[i]
            current_peak_idx = i
        dd = (running_max - values[i]) / running_max
        if dd > worst_dd:
            worst_dd = dd
            worst_peak_idx = current_peak_idx
            worst_trough_idx = i

    dd_pct = round(worst_dd * 100, 1)

    if dd_pct > 50:
        signal = "extreme_risk"
    elif dd_pct > 30:
        signal = "high_risk"
    elif dd_pct > 15:
        signal = "moderate_risk"
    else:
        signal = "low_risk"

    return MaxDrawdownResult(
        value=dd_pct,
        worst_start=dates[worst_peak_idx],
        worst_end=dates[worst_trough_idx],
        annualized_vol=round(annualized_vol, 1),
        signal=signal,
    )


def historical_stress_test(
    holdings_prices: dict[str, dict[str, float]],
    weights: list[float],
    tickers: list[str],
    start_date: str,
    end_date: str,
    scenario_name: str,
    portfolio_value: float,
) -> StressScenarioResult:
    """Replay a historical period using actual price data.

    ``holdings_prices`` maps ticker -> {date_str: close_price} for the
    scenario date range.  ``weights`` and ``tickers`` define the current
    portfolio composition.  Returns actual per-holding and portfolio returns.
    """
    if len(weights) != len(tickers):
        raise ValueError("weights and tickers must be the same length")

    holdings_impact = []
    covered_weight = 0.0
    weighted_return = 0.0

    for ticker, weight in zip(tickers, weights):
        prices = holdings_prices.get(ticker)
        if not prices:
            holdings_impact.append({
                "ticker": ticker,
                "return_pct": None,
                "dollar_impact": None,
                "note": "no data for this period",
            })
            continue

        # Sort by date to get first and last price in the period
        sorted_dates = sorted(prices.keys())
        first_price = prices[sorted_dates[0]]
        last_price = prices[sorted_dates[-1]]

        if first_price == 0:
            holdings_impact.append({
                "ticker": ticker,
                "return_pct": None,
                "dollar_impact": None,
                "note": "zero starting price",
            })
            continue

        holding_return = (last_price - first_price) / first_price
        dollar_impact = weight * portfolio_value * holding_return

        holdings_impact.append({
            "ticker": ticker,
            "return_pct": round(holding_return * 100, 1),
            "dollar_impact": round(dollar_impact, 2),
        })

        covered_weight += weight
        weighted_return += weight * holding_return

    # Renormalize portfolio return over covered weight so missing holdings
    # don't artificially mute the impact (fix #2)
    if covered_weight > 0 and covered_weight < 1.0:
        portfolio_return = weighted_return / covered_weight
    else:
        portfolio_return = weighted_return

    coverage_pct = round(covered_weight * 100, 1)

    return StressScenarioResult(
        scenario_name=scenario_name,
        period=f"{start_date} to {end_date}",
        portfolio_impact_pct=round(portfolio_return * 100, 1),
        portfolio_impact_dollar=round(portfolio_return * portfolio_value, 2),
        holdings_impact=holdings_impact,
        coverage_pct=coverage_pct,
    )


def worst_period(
    portfolio_values: list[float],
    dates: list[str],
    window_days: int = 30,
) -> StressScenarioResult:
    """Find the worst N-day period in the portfolio's history.

    Uses a rolling window over the portfolio value time series to find
    the period with the largest decline.
    """
    if len(portfolio_values) != len(dates):
        raise ValueError("portfolio_values and dates must be the same length")
    if len(portfolio_values) < window_days + 1:
        raise ValueError(
            f"Need at least {window_days + 1} data points, got {len(portfolio_values)}"
        )

    worst_return = 0.0
    worst_start_idx = 0
    worst_end_idx = window_days

    for i in range(len(portfolio_values) - window_days):
        start_val = portfolio_values[i]
        end_val = portfolio_values[i + window_days]
        if start_val == 0:
            continue
        ret = (end_val - start_val) / start_val
        if ret < worst_return:
            worst_return = ret
            worst_start_idx = i
            worst_end_idx = i + window_days

    current_value = portfolio_values[-1]

    return StressScenarioResult(
        scenario_name=f"Worst {window_days}-Day Period",
        period=f"{dates[worst_start_idx]} to {dates[worst_end_idx]}",
        portfolio_impact_pct=round(worst_return * 100, 1),
        portfolio_impact_dollar=round(worst_return * current_value, 2),
        holdings_impact=[],  # not broken down per-holding for rolling window
    )


# ---------------------------------------------------------------------------
# Risk Grade
# ---------------------------------------------------------------------------


def _linear_penalty(value: float, safe: float, danger: float, max_penalty: float) -> float:
    """Linear interpolation between safe (0 penalty) and danger (max penalty)."""
    if value <= safe:
        return 0.0
    if value >= danger:
        return max_penalty
    return (value - safe) / (danger - safe) * max_penalty


def risk_grade(
    conc: ConcentrationResult,
    corr: CorrelationResult | None,
    leverage: EffectiveLeverageResult,
    beta_result: PortfolioBetaResult,
    drawdown: MaxDrawdownResult,
) -> RiskGradeResult:
    """Transparent risk grade with visible per-component penalties.

    Total budget: 100 points.  Each component deducts a penalty.
    Score = 100 - total_penalties.  Correlation is optional (needs 2+ holdings).
    """
    components: dict[str, dict] = {}

    # Concentration: max 25 penalty.  HHI 0.10 = safe, 0.40 = danger.
    conc_penalty = _linear_penalty(conc.herfindahl_index, 0.10, 0.40, 25)
    components["concentration"] = {
        "penalty": round(conc_penalty, 1),
        "max_penalty": 25,
        "reason": f"HHI is {conc.herfindahl_index:.2f}, "
        f"top holding is {conc.top_holding_pct:.0f}% of portfolio",
    }

    # Correlation: max 20 penalty.  avg 0.30 = safe, 0.90 = danger.
    if corr is not None:
        corr_penalty = _linear_penalty(corr.avg_pairwise, 0.30, 0.90, 20)
        components["correlation"] = {
            "penalty": round(corr_penalty, 1),
            "max_penalty": 20,
            "reason": f"average pairwise correlation is {corr.avg_pairwise:.2f}, "
            f"most correlated: {corr.max_pair[0]}/{corr.max_pair[1]} ({corr.max_pair[2]:.2f})",
        }
    else:
        corr_penalty = 0.0
        components["correlation"] = {
            "penalty": 0.0,
            "max_penalty": 20,
            "reason": "only 1 holding, correlation not applicable",
        }

    # Leverage: max 25 penalty.  1.0 = safe, 3.0 = danger.
    lev_penalty = _linear_penalty(leverage.value, 1.0, 3.0, 25)
    components["leverage"] = {
        "penalty": round(lev_penalty, 1),
        "max_penalty": 25,
        "reason": f"effective leverage is {leverage.value:.1f}x, "
        f"{leverage.leveraged_pct:.0f}% of portfolio in leveraged products",
    }

    # Beta: max 15 penalty.  1.0 = safe, 3.0 = danger.
    beta_penalty = _linear_penalty(beta_result.value, 1.0, 3.0, 15)
    components["beta"] = {
        "penalty": round(beta_penalty, 1),
        "max_penalty": 15,
        "reason": f"portfolio beta is {beta_result.value:.2f} — "
        f"{beta_result.interpretation}",
    }

    # Drawdown: max 15 penalty.  10% = safe, 60% = danger.
    dd_penalty = _linear_penalty(drawdown.value, 10.0, 60.0, 15)
    components["drawdown"] = {
        "penalty": round(dd_penalty, 1),
        "max_penalty": 15,
        "reason": f"historical max drawdown is {drawdown.value:.1f}%, "
        f"worst period: {drawdown.worst_start} to {drawdown.worst_end}",
    }

    total_penalty = conc_penalty + corr_penalty + lev_penalty + beta_penalty + dd_penalty
    score = max(0, round(100 - total_penalty, 1))

    if score >= 80:
        grade = "A"
        interpretation = "Low risk — well diversified with moderate leverage and volatility"
    elif score >= 65:
        grade = "B"
        interpretation = "Below-average risk — some concentration or leverage exposure"
    elif score >= 50:
        grade = "C"
        interpretation = "Moderate risk — notable concentration, correlation, or leverage"
    elif score >= 35:
        grade = "D"
        interpretation = "High risk — significant concentration, leverage, or volatility"
    else:
        grade = "F"
        interpretation = "Very high risk — extreme concentration, leverage, and/or correlation"

    return RiskGradeResult(
        grade=grade,
        score=score,
        components=components,
        interpretation=interpretation,
    )
