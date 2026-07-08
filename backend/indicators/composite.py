"""Composite scoring — combine 7 indicators into Buy/Hold/Sell signal."""

from __future__ import annotations

from indicators.models import (
    ATRResult,
    BetaResult,
    BollingerResult,
    CompositeResult,
    MACDResult,
    RSIResult,
    SMACrossoverResult,
    SharpeResult,
)

# Weights must sum to 1.0
WEIGHTS: dict[str, float] = {
    "rsi": 0.15,
    "macd": 0.15,
    "bollinger": 0.10,
    "sma_crossover": 0.15,
    "atr": 0.10,
    "beta": 0.15,
    "sharpe": 0.20,
}


def normalize_signal(name: str, result: object) -> float:
    """Map an indicator result to a value in [-1, +1].

    +1 = strongly bullish, -1 = strongly bearish, 0 = neutral.
    """
    if isinstance(result, RSIResult):
        # RSI 30 -> +1 (oversold/bullish), 50 -> 0, 70 -> -1 (overbought/bearish)
        return max(-1.0, min(1.0, (50 - result.value) / 20))

    if isinstance(result, MACDResult):
        # Histogram magnitude, clamped to [-1, 1]
        if result.histogram == 0:
            return 0.0
        # Normalize by the absolute MACD line to make it scale-independent
        scale = abs(result.macd_line) if result.macd_line != 0 else 1.0
        return max(-1.0, min(1.0, result.histogram / scale))

    if isinstance(result, BollingerResult):
        # Low volatility (narrow bands) = bullish, high = bearish
        if result.signal == "low_volatility":
            return 0.5
        elif result.signal == "high_volatility":
            return -0.5
        return 0.0

    if isinstance(result, SMACrossoverResult):
        # Golden cross = bullish, death cross = bearish, decaying over time
        if result.crossover_type == "golden_cross":
            decay = max(0.2, 1.0 - (result.days_since_cross or 0) / 100)
            return decay
        elif result.crossover_type == "death_cross":
            decay = max(0.2, 1.0 - (result.days_since_cross or 0) / 100)
            return -decay
        return 0.0

    if isinstance(result, ATRResult):
        # Lower ATR% = more stable = bullish, higher = riskier = bearish
        # ATR% < 1% -> +0.5, 1-2% -> 0, 2-4% -> -0.5, >4% -> -1
        if result.atr_percent < 1.0:
            return 0.5
        elif result.atr_percent < 2.0:
            return 0.0
        elif result.atr_percent < 4.0:
            return -0.5
        return -1.0

    if isinstance(result, BetaResult):
        # Beta < 0.8 -> defensive/bullish, 0.8-1.2 -> neutral, >1.2 -> risky/bearish
        if result.value < 0.8:
            return 0.5
        elif result.value <= 1.2:
            return 0.0
        elif result.value <= 1.5:
            return -0.3
        return -0.7

    if isinstance(result, SharpeResult):
        # Sharpe > 2 -> strongly bullish, 1 -> bullish, 0 -> neutral, <0 -> bearish
        return max(-1.0, min(1.0, result.value / 2))

    raise ValueError(f"Unknown indicator: {name}")


def composite_score(
    results: dict[str, object],
) -> CompositeResult:
    """Compute weighted composite score from available indicator results.

    ``results`` maps indicator names (e.g. "rsi", "macd") to their result
    dataclasses.  Missing indicators are excluded and remaining weights are
    re-normalized.
    """
    contributions: dict[str, float] = {}
    total_weight = 0.0
    weighted_sum = 0.0

    for name, weight in WEIGHTS.items():
        if name not in results:
            continue
        normalized = normalize_signal(name, results[name])
        contribution = normalized * weight
        contributions[name] = round(contribution, 4)
        weighted_sum += contribution
        total_weight += weight

    # Re-normalize if some indicators are missing
    if total_weight > 0 and total_weight < 1.0:
        score = weighted_sum / total_weight
    elif total_weight > 0:
        score = weighted_sum
    else:
        score = 0.0

    score = max(-1.0, min(1.0, score))

    # Signal classification
    if score > 0.25:
        signal = "buy"
    elif score < -0.25:
        signal = "sell"
    else:
        signal = "hold"

    # Confidence: based on score magnitude and indicator agreement
    agreement = _indicator_agreement(contributions)
    confidence = min(1.0, (abs(score) * 0.7 + agreement * 0.3))

    return CompositeResult(
        score=round(score, 4),
        signal=signal,
        confidence=round(confidence, 2),
        contributions=contributions,
    )


def _indicator_agreement(contributions: dict[str, float]) -> float:
    """Measure how much indicators agree (0 = split, 1 = unanimous)."""
    if not contributions:
        return 0.0
    signs = [1 if v > 0 else (-1 if v < 0 else 0) for v in contributions.values()]
    non_zero = [s for s in signs if s != 0]
    if not non_zero:
        return 0.0
    majority = abs(sum(non_zero)) / len(non_zero)
    return majority
