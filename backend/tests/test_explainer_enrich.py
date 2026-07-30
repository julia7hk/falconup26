"""Tests for the LLM enrichment orchestrator (`llm_explainer.explain`, M8 PR2).

No network — `client.generate` is monkeypatched to stand in for the model. The
orchestrator's contract is the whole safety story of the feature: use the LLM
rephrasing only when it comes back AND passes validation, otherwise serve the
deterministic PR1 text, seamlessly, tagging which path served the response.
"""

from __future__ import annotations

from dataclasses import asdict

import pytest

import llm_explainer
from llm_explainer import explain
from llm_explainer.templates import explain_grade
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
    weights = [0.6, 0.4]
    conc = concentration(weights, ["Technology", "Technology"])
    corr = correlation_matrix(
        {"QQQ": [0.01, -0.02, 0.03, -0.01, 0.02], "TQQQ": [0.03, -0.06, 0.09, -0.03, 0.06]}
    )
    lev = effective_leverage(weights, [1.0, 3.0])
    beta = portfolio_beta(weights, [1.0, 3.0])
    vals = [100.0 + (i if i < 30 else 60 - i) for i in range(60)]
    dates = [f"2024-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(60)]
    dd = max_drawdown(vals, dates)
    return asdict(risk_grade(conc, corr, lev, beta, dd))


def _valid_rephrasing(baseline: dict) -> dict:
    """A faithful rephrasing that introduces no new numbers/tickers."""
    return {
        "headline": "Your portfolio landed at a grade worth understanding.",
        "overview": "Overall this leans risky, mostly down to leverage.",
        "components": [
            {"key": c["key"], "detail": "A calm restatement, no new figures."}
            for c in baseline["components"]
        ],
    }


class TestExplainOrchestrator:
    def test_no_llm_output_falls_back(self, grade, monkeypatch):
        # client.generate returns None (no key / refusal / timeout) → PR1 text.
        monkeypatch.setattr(llm_explainer.client, "generate", lambda _ex: None)
        result = explain(grade)
        assert result["source"] == "deterministic"
        baseline = explain_grade(grade)
        assert {k: v for k, v in result.items() if k != "source"} == baseline

    def test_valid_rephrasing_is_used(self, grade, monkeypatch):
        baseline = explain_grade(grade)
        monkeypatch.setattr(
            llm_explainer.client, "generate", lambda _ex: _valid_rephrasing(baseline)
        )
        result = explain(grade)
        assert result["source"] == "llm"
        assert result["headline"] == "Your portfolio landed at a grade worth understanding."
        assert result["components"][0]["detail"] == "A calm restatement, no new figures."
        # Static/numeric fields survive untouched.
        assert result["components"][0]["label"] == baseline["components"][0]["label"]
        assert result["components"][0]["penalty"] == baseline["components"][0]["penalty"]

    def test_hallucinated_output_falls_back(self, grade, monkeypatch):
        def _bad(_ex):
            return {
                "headline": "Your portfolio crashed 88% and you should buy AAPL.",
                "overview": "",
                "components": [],
            }

        monkeypatch.setattr(llm_explainer.client, "generate", _bad)
        result = explain(grade)
        # Fabricated number + hallucinated ticker → rejected, PR1 text served.
        assert result["source"] == "deterministic"
        assert result["headline"] == explain_grade(grade)["headline"]

    def test_partial_rephrasing_keeps_deterministic_fields(self, grade, monkeypatch):
        baseline = explain_grade(grade)
        # Model returns only a headline; overview + details fall back per-field.
        monkeypatch.setattr(
            llm_explainer.client,
            "generate",
            lambda _ex: {"headline": "A gentler headline.", "overview": "", "components": []},
        )
        result = explain(grade)
        assert result["source"] == "llm"
        assert result["headline"] == "A gentler headline."
        assert result["overview"] == baseline["overview"]
        assert [c["detail"] for c in result["components"]] == [
            c["detail"] for c in baseline["components"]
        ]
