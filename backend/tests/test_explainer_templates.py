"""Tests for the deterministic explainer templates.

Two things matter here: the phrasing is right (labels, severity buckets, top
drivers), and — the non-negotiable — every number and ticker in the output
traces back to the input payload. The second guard is what PR2's LLM validator
will enforce against the model; the deterministic templates must pass it too.

Uses real `risk_grade` payloads built from the risk math, so the input shape
can never drift from what the endpoint actually feeds in.
"""

from __future__ import annotations

import re
from dataclasses import asdict

import pytest

from llm_explainer.templates import DISCLAIMER, _severity, explain_grade
from risk.math import (
    concentration,
    correlation_matrix,
    effective_leverage,
    max_drawdown,
    portfolio_beta,
    risk_grade,
)


# ---------------------------------------------------------------------------
# Fixtures: real risk_grade payloads (no mocking of the engine)
# ---------------------------------------------------------------------------


def _grade_payload(
    weights: list[float],
    sectors: list[str],
    leverage_factors: list[float],
    betas: list[float],
    returns_by_ticker: dict[str, list[float]] | None,
) -> dict:
    """Build a real risk_grade dict from the risk math, like the endpoint does."""
    conc = concentration(weights, sectors)
    corr = correlation_matrix(returns_by_ticker) if returns_by_ticker else None
    lev = effective_leverage(weights, leverage_factors)
    beta = portfolio_beta(weights, betas)
    # A 60-point value series with a real peak-to-trough decline.
    vals = [100.0 + (i if i < 30 else 60 - i) for i in range(60)]
    dates = [f"2024-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(60)]
    dd = max_drawdown(vals, dates)
    return asdict(risk_grade(conc, corr, lev, beta, dd))


@pytest.fixture
def concentrated_leveraged() -> dict:
    """High-risk portfolio: two correlated tech ETFs, one 3x leveraged."""
    return _grade_payload(
        weights=[0.6, 0.4],
        sectors=["Technology", "Technology"],
        leverage_factors=[1.0, 3.0],
        betas=[1.0, 3.0],
        returns_by_ticker={
            "QQQ": [0.01, -0.02, 0.03, -0.01, 0.02],
            "TQQQ": [0.03, -0.06, 0.09, -0.03, 0.06],
        },
    )


@pytest.fixture
def diversified() -> dict:
    """Lower-risk portfolio: four unleveraged holdings across sectors."""
    return _grade_payload(
        weights=[0.25, 0.25, 0.25, 0.25],
        sectors=["Technology", "Healthcare", "Energy", "Finance"],
        leverage_factors=[1.0, 1.0, 1.0, 1.0],
        betas=[1.0, 0.9, 1.1, 1.0],
        returns_by_ticker={
            "AAA": [0.01, -0.02, 0.03, -0.01],
            "BBB": [-0.01, 0.02, -0.01, 0.02],
            "CCC": [0.02, 0.01, -0.02, -0.01],
            "DDD": [-0.02, -0.01, 0.02, 0.03],
        },
    )


# ---------------------------------------------------------------------------
# Shape + phrasing
# ---------------------------------------------------------------------------


class TestShape:
    def test_top_level_fields(self, concentrated_leveraged):
        ex = explain_grade(concentrated_leveraged)
        assert ex["grade"] == concentrated_leveraged["grade"]
        assert ex["score"] == concentrated_leveraged["score"]
        assert ex["disclaimer"] == DISCLAIMER
        assert isinstance(ex["headline"], str) and ex["headline"]
        assert isinstance(ex["overview"], str) and ex["overview"]

    def test_headline_states_grade_and_score(self, concentrated_leveraged):
        ex = explain_grade(concentrated_leveraged)
        assert str(concentrated_leveraged["score"]) in ex["headline"]
        assert concentrated_leveraged["grade"] in ex["headline"]

    def test_one_section_per_component(self, concentrated_leveraged):
        ex = explain_grade(concentrated_leveraged)
        assert {s["key"] for s in ex["components"]} == set(
            concentrated_leveraged["components"].keys()
        )

    def test_sections_carry_penalty_and_meaning(self, concentrated_leveraged):
        ex = explain_grade(concentrated_leveraged)
        for s in ex["components"]:
            src = concentrated_leveraged["components"][s["key"]]
            assert s["penalty"] == src["penalty"]
            assert s["max_penalty"] == src["max_penalty"]
            assert s["meaning"]  # non-empty educational blurb
            assert s["label"]
            # The engine's factual reason must survive into the detail text
            # (the template only capitalizes its first letter).
            assert src["reason"].rstrip(".").lower() in s["detail"].lower()

    def test_disclaimer_is_not_advice(self, concentrated_leveraged):
        ex = explain_grade(concentrated_leveraged)
        assert "not financial advice" in ex["disclaimer"].lower()


class TestSeverity:
    def test_bucket_boundaries(self):
        assert _severity(0, 25)[0] == "none"
        assert _severity(2, 25)[0] == "low"       # 0.08
        assert _severity(10, 25)[0] == "moderate"  # 0.40
        assert _severity(18, 25)[0] == "high"      # 0.72
        assert _severity(25, 25)[0] == "severe"    # 1.0

    def test_zero_max_penalty_is_none(self):
        # Defensive: never divide-by-zero, treat as no contribution.
        assert _severity(0, 0)[0] == "none"

    def test_maxed_component_is_severe(self, concentrated_leveraged):
        ex = explain_grade(concentrated_leveraged)
        conc = next(s for s in ex["components"] if s["key"] == "concentration")
        # 0.6/0.4 single-sector -> maxed concentration penalty.
        assert conc["severity"] == "severe"
        assert "biggest risks" in conc["detail"]


class TestTopDrivers:
    def test_names_highest_penalty_components(self, concentrated_leveraged):
        ex = explain_grade(concentrated_leveraged)
        ranked = sorted(
            concentrated_leveraged["components"].items(),
            key=lambda kv: kv[1]["penalty"],
            reverse=True,
        )
        top_two_labels = [k for k, _ in ranked[:2]]
        # Both top drivers should be referenced by their component name.
        for key in top_two_labels:
            assert key in ex["overview"].lower()

    def test_low_risk_has_no_alarming_drivers(self, diversified):
        ex = explain_grade(diversified)
        # A clean portfolio may still carry small penalties, but nothing severe.
        assert all(s["severity"] != "severe" for s in ex["components"])


# ---------------------------------------------------------------------------
# Traceability: every number/ticker in the output appears in the input
# ---------------------------------------------------------------------------


def _numbers(text: str) -> set[str]:
    """All numeric tokens (ints/decimals) in a string."""
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def _tickers(text: str) -> set[str]:
    """Uppercase alpha tokens 2-5 chars — candidate tickers."""
    return set(re.findall(r"\b[A-Z]{2,5}\b", text))


def _input_number_corpus(grade: dict) -> str:
    """Everything the engine put in the payload, as one searchable string."""
    parts = [str(grade["score"]), grade["grade"], grade["interpretation"]]
    for comp in grade["components"].values():
        parts += [str(comp["penalty"]), str(comp["max_penalty"]), comp["reason"]]
    return " ".join(parts)


def _output_text(ex: dict) -> str:
    parts = [ex["headline"], ex["overview"]]
    for s in ex["components"]:
        parts += [s["detail"], str(s["penalty"]), str(s["max_penalty"])]
    return " ".join(parts)


class TestTraceability:
    @pytest.mark.parametrize("fixture", ["concentrated_leveraged", "diversified"])
    def test_every_output_number_traces_to_input(self, fixture, request):
        grade = request.getfixturevalue(fixture)
        ex = explain_grade(grade)
        corpus = _input_number_corpus(grade)
        out_numbers = _numbers(_output_text(ex))
        # The only "100" is the fixed /100 scale in the headline — allow it.
        untraceable = {
            n for n in out_numbers if n != "100" and n not in corpus
        }
        assert not untraceable, f"fabricated numbers: {untraceable}"

    def test_every_output_ticker_traces_to_input(self, concentrated_leveraged):
        ex = explain_grade(concentrated_leveraged)
        # Tickers only ever enter via the correlation reason (max_pair).
        input_tickers = _tickers(
            concentrated_leveraged["components"]["correlation"]["reason"]
        )
        # Detail text is the only place a ticker could appear.
        detail_text = " ".join(s["detail"] for s in ex["components"])
        for t in _tickers(detail_text):
            # HHI is an all-caps word but not a ticker; the guard is that any
            # ticker-shaped token in the output that looks like a symbol must
            # have come from the input's correlation reason.
            if t in {"HHI"}:
                continue
            assert t in input_tickers, f"untraceable ticker-like token: {t}"
