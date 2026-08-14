"""Tests for the LLM-output validator (M8 PR2 anti-hallucination gate).

Pure logic, no network. The gate must accept faithful rephrasings and reject
any output that introduces a number or ticker the risk engine didn't produce —
that's the whole safety promise of the LLM layer (bad output → fall back to the
deterministic text). Uses a real `risk_grade` payload so the input shape can't
drift from what the endpoint feeds in.
"""

from __future__ import annotations

from dataclasses import asdict

import pytest

from llm_explainer.templates import explain_grade
from llm_explainer.validator import is_valid
from risk.math import (
    concentration,
    correlation_matrix,
    effective_leverage,
    max_drawdown,
    portfolio_beta,
    risk_grade,
)


@pytest.fixture
def grade() -> dict:
    """A real high-risk grade: two correlated tech ETFs, one 3x leveraged."""
    weights = [0.6, 0.4]
    conc = concentration(weights, ["Technology", "Technology"])
    # Correlated return series so the correlation reason names QQQ/TQQQ.
    corr = correlation_matrix(
        {"QQQ": [0.01, -0.02, 0.03, -0.01, 0.02], "TQQQ": [0.03, -0.06, 0.09, -0.03, 0.06]}
    )
    lev = effective_leverage(weights, [1.0, 3.0])
    beta = portfolio_beta(weights, [1.0, 3.0])
    vals = [100.0 + (i if i < 30 else 60 - i) for i in range(60)]
    dates = [f"2024-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(60)]
    dd = max_drawdown(vals, dates)
    return asdict(risk_grade(conc, corr, lev, beta, dd))


def _enriched(grade: dict, headline="", overview="", details=None) -> dict:
    """A minimal enriched-shape payload for the validator (dynamic fields only)."""
    details = details or {}
    baseline = explain_grade(grade)
    return {
        "headline": headline,
        "overview": overview,
        "components": [
            {"key": c["key"], "detail": details.get(c["key"], "")}
            for c in baseline["components"]
        ],
    }


class TestValidator:
    def test_deterministic_output_passes(self, grade):
        # The PR1 text is built from the same corpus, so it must always validate —
        # if it didn't, the guard would reject legitimate output.
        assert is_valid(explain_grade(grade), grade) is True

    def test_faithful_rephrasing_passes(self, grade):
        score = grade["score"]
        ex = _enriched(
            grade,
            headline=f"Your portfolio earned a {grade['grade']} — {score} out of 100.",
            overview="Overall this is a riskier mix, mostly because of leverage.",
            details={"leverage": "A chunk of your money sits in a leveraged fund."},
        )
        assert is_valid(ex, grade) is True

    def test_fabricated_number_fails(self, grade):
        ex = _enriched(grade, overview="Your portfolio dropped 42% last quarter.")
        assert is_valid(ex, grade) is False

    def test_bare_small_integers_in_prose_pass(self, grade):
        # Single digits 0-3 are educational/prose ("a beta above 1", "2x or 3x
        # ETFs", "a few holdings"), never this portfolio's figures. Rejecting
        # them made the guard fall back to deterministic text ~half the time.
        ex = _enriched(
            grade,
            overview="A beta above 1 means bigger swings than the market.",
            details={"leverage": "Leveraged funds like 2x or 3x ETFs magnify moves."},
        )
        assert is_valid(ex, grade) is True

    def test_fabricated_single_digit_figure_still_fails(self, grade):
        # The exemption is only for bare integers 0-3; a fabricated percentage
        # using a larger single-ish figure must still be caught.
        ex = _enriched(grade, overview="Your portfolio dropped 7% last week.")
        assert is_valid(ex, grade) is False

    def test_hallucinated_ticker_fails(self, grade):
        ex = _enriched(grade, overview="You should really look at AAPL and NVDA.")
        assert is_valid(ex, grade) is False

    def test_input_tickers_allowed(self, grade):
        # QQQ/TQQQ come from the correlation reason, so naming them is fine.
        ex = _enriched(grade, overview="QQQ and TQQQ tend to move together.")
        assert is_valid(ex, grade) is True

    def test_finance_acronyms_allowed(self, grade):
        ex = _enriched(grade, overview="Leveraged ETF products amplify moves.")
        assert is_valid(ex, grade) is True

    def test_scale_100_allowed(self, grade):
        ex = _enriched(grade, headline="A score out of 100 is just a starting point.")
        assert is_valid(ex, grade) is True

    def test_meaning_copy_is_not_checked(self, grade):
        # Static `meaning` prose ("2x or 3x ETFs") carries illustrative numbers;
        # the guard must ignore it, only checking the fields the model rephrased.
        ex = _enriched(grade, overview="Nothing alarming here.")
        ex["components"][0]["meaning"] = "Leverage like 2x or 3x ETFs magnifies moves."
        assert is_valid(ex, grade) is True
