"""Data models for indicator results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RSIResult:
    """Relative Strength Index (14-day)."""

    value: float  # 0-100
    signal: str  # "oversold", "overbought", "neutral"


@dataclass(frozen=True, slots=True)
class MACDResult:
    """Moving Average Convergence Divergence (12/26/9)."""

    macd_line: float
    signal_line: float
    histogram: float
    signal: str  # "bullish", "bearish", "neutral"


@dataclass(frozen=True, slots=True)
class BollingerResult:
    """Bollinger Band width (20-day, 2 sigma)."""

    width: float  # (upper - lower) / middle, normalized
    upper: float
    lower: float
    signal: str  # "high_volatility", "low_volatility", "neutral"


@dataclass(frozen=True, slots=True)
class SMACrossoverResult:
    """50/200-day SMA crossover."""

    sma_50: float
    sma_200: float
    crossover_type: str  # "golden_cross", "death_cross", "none"
    days_since_cross: int | None


@dataclass(frozen=True, slots=True)
class ATRResult:
    """Average True Range (14-day)."""

    value: float  # ATR in price terms
    atr_percent: float  # ATR as % of current price


@dataclass(frozen=True, slots=True)
class BetaResult:
    """Beta vs S&P 500 (1-year)."""

    value: float
    interpretation: str


@dataclass(frozen=True, slots=True)
class SharpeResult:
    """Sharpe ratio (1-year, annualized)."""

    value: float
    risk_free_rate: float  # annual rate used
    interpretation: str


@dataclass(frozen=True, slots=True)
class CompositeResult:
    """Weighted composite of all indicators."""

    score: float  # -1 to +1
    signal: str  # "buy", "hold", "sell"
    confidence: float  # 0 to 1
    contributions: dict[str, float]  # per-indicator weighted contribution
    directions: dict[str, str]  # per-indicator direction: "bullish", "bearish", "neutral"
