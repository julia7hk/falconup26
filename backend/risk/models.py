"""Data models for portfolio risk results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConcentrationResult:
    """Herfindahl index + sector exposure breakdown."""

    herfindahl_index: float  # 0-1, higher = more concentrated
    top_holding_pct: float  # largest single holding as % of portfolio
    sector_breakdown: dict[str, float]  # sector -> % of portfolio value
    signal: str  # "highly_concentrated", "moderate", "diversified"


@dataclass(frozen=True, slots=True)
class CorrelationResult:
    """Pairwise correlation matrix of portfolio holdings."""

    matrix: dict[str, dict[str, float]]  # ticker -> ticker -> correlation
    avg_pairwise: float  # average of all pairwise correlations
    max_pair: tuple[str, str, float]  # most correlated pair
    signal: str  # "highly_correlated", "moderate", "diversified"


@dataclass(frozen=True, slots=True)
class EffectiveLeverageResult:
    """Weighted average leverage factor across portfolio."""

    value: float  # weighted average leverage
    leveraged_pct: float  # % of portfolio in leveraged products
    signal: str  # "extreme", "high", "moderate", "none"


@dataclass(frozen=True, slots=True)
class PortfolioBetaResult:
    """Weighted portfolio beta vs S&P 500."""

    value: float
    interpretation: str


@dataclass(frozen=True, slots=True)
class MaxDrawdownResult:
    """Actual historical max drawdown from portfolio value time series."""

    value: float  # max drawdown as %, e.g. 45.0 means -45%
    worst_start: str  # ISO date of peak before worst drawdown
    worst_end: str  # ISO date of trough
    annualized_vol: float  # portfolio annualized volatility
    signal: str  # "extreme_risk", "high_risk", "moderate_risk", "low_risk"


@dataclass(frozen=True, slots=True)
class StressScenarioResult:
    """Portfolio impact from replaying a real historical market event."""

    scenario_name: str
    period: str  # e.g. "2020-02-19 to 2020-03-23"
    portfolio_impact_pct: float  # total portfolio return during period
    portfolio_impact_dollar: float  # dollar impact based on current value
    holdings_impact: list[dict]  # per-holding: ticker, return_pct, dollar_impact
    coverage_pct: float = 100.0  # % of portfolio weight with data for this period


@dataclass(frozen=True, slots=True)
class RiskGradeResult:
    """Transparent risk grade with visible per-component penalties."""

    grade: str  # A through F
    score: float  # 0-100, higher = safer
    components: dict[str, dict]  # name -> {penalty, max_penalty, reason}
    interpretation: str
