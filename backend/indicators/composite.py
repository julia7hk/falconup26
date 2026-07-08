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


def _clamp(value: float) -> float:
    """Clamp to [-1, +1]."""
    return max(-1.0, min(1.0, value))


def normalize_signal(name: str, result: object) -> float:
    """Map an indicator result to a value in [-1, +1].

    +1 = strongly bullish, -1 = strongly bearish, 0 = neutral.
    All mappings use smooth linear interpolation (no discrete buckets).
    """
    if isinstance(result, RSIResult):
        # RSI 30 -> +1 (oversold/bullish), 50 -> 0, 70 -> -1 (overbought/bearish)
        return _clamp((50 - result.value) / 20)

    if isinstance(result, MACDResult):
        # Positive histogram = bullish, negative = bearish.
        # Normalize by signal line magnitude for scale independence.
        # Falls back to raw histogram sign if signal line is near zero.
        scale = max(abs(result.signal_line), abs(result.macd_line), 0.01)
        return _clamp(result.histogram / scale * 1.5)

    if isinstance(result, BollingerResult):
        # Smooth: width 0.02 (2%) -> +0.8 (tight, bullish),
        #         width 0.06 (6%) -> 0 (average),
        #         width 0.12 (12%) -> -1.0 (wide, bearish)
        # Linear interpolation centered on 0.06 typical width
        return _clamp((0.06 - result.width) / 0.06 * 1.0)

    if isinstance(result, SMACrossoverResult):
        # Golden cross = bullish, death cross = bearish.
        # Slower decay: full strength for 30 days, fades over 200 days, floor at 0.3
        if result.crossover_type == "golden_cross":
            days = result.days_since_cross or 0
            decay = max(0.3, 1.0 - max(0, days - 30) / 170)
            return decay
        elif result.crossover_type == "death_cross":
            days = result.days_since_cross or 0
            decay = max(0.3, 1.0 - max(0, days - 30) / 170)
            return -decay
        # No crossover: use SMA gap as a weaker directional signal
        gap = (result.sma_50 - result.sma_200) / result.sma_200 if result.sma_200 != 0 else 0
        return _clamp(gap * 10)  # 1% gap -> 0.1 signal

    if isinstance(result, ATRResult):
        # Smooth: ATR% 0.5 -> +0.6 (very stable),
        #         ATR% 2.0 -> 0 (average),
        #         ATR% 4.5 -> -0.8 (very volatile)
        return _clamp((2.0 - result.atr_percent) / 2.0 * 0.8)

    if isinstance(result, BetaResult):
        # Smooth: beta 0.5 -> +0.5 (defensive),
        #         beta 1.0 -> 0 (market),
        #         beta 2.0 -> -1.0 (very volatile)
        return _clamp((1.0 - result.value) * 1.0)

    if isinstance(result, SharpeResult):
        # Sharpe 2+ -> +1, 1 -> +0.5, 0 -> 0, -1 -> -0.5
        return _clamp(result.value / 2)

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
    directions: dict[str, str] = {}
    total_weight = 0.0
    weighted_sum = 0.0

    for name, weight in WEIGHTS.items():
        if name not in results:
            continue
        normalized = normalize_signal(name, results[name])
        contribution = normalized * weight
        contributions[name] = round(contribution, 4)
        if normalized > 0.05:
            directions[name] = "bullish"
        elif normalized < -0.05:
            directions[name] = "bearish"
        else:
            directions[name] = "neutral"
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

    # Signal classification — lower thresholds so moderate agreement triggers
    if score > 0.15:
        signal = "buy"
    elif score < -0.15:
        signal = "sell"
    else:
        signal = "hold"

    # Confidence: weight agreement more heavily than raw score magnitude
    agreement = _indicator_agreement(contributions)
    confidence = min(1.0, (abs(score) * 0.4 + agreement * 0.6))

    return CompositeResult(
        score=round(score, 4),
        signal=signal,
        confidence=round(confidence, 2),
        contributions=contributions,
        directions=directions,
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
