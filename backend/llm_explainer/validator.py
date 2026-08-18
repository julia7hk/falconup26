"""The anti-hallucination gate (M8 PR2).

Pure logic, no I/O — deliberately split from ``client.py`` so it's testable
with plain strings and can't be broken by an API change. It answers one
question: does every number and ticker in the LLM's rephrased text trace back
to the structured facts the engine produced? If not, the caller discards the
LLM output and serves the deterministic PR1 text.

This mirrors, verbatim in spirit, the traceability guard the deterministic
templates are themselves tested against
(``tests/test_explainer_templates.py::TestTraceability``). The scoping rule is
the same and non-negotiable: only the *dynamic* fields the model rephrased
(``headline``, ``overview``, each component ``detail``) are checked — never the
static ``meaning`` copy, which is trusted educational prose that legitimately
carries illustrative figures ("2x or 3x ETFs") describing the concept, not this
portfolio.
"""

from __future__ import annotations

import re

# Uppercase acronyms that are finance vocabulary, not portfolio holdings. A
# rephrase may legitimately say "ETF" or "HHI" without it being a hallucinated
# ticker, so they never count against the ticker-traceability check.
_ALLOWED_ACRONYMS = frozenset({"HHI", "ETF", "ETFS", "US", "USA", "AI"})

# Numbers a rephrase may use without tracing to the input:
#   "100" — the fixed "/100" grade scale the headline states ("scored X out of 100").
#   "0"-"3" — bare single digits that recur in natural and educational prose, not
#     as this portfolio's figures: "a beta above 1", "leveraged funds like 2x or 3x
#     ETFs", "a few holdings". This mirrors why the static `meaning` copy is exempt
#     (see module docstring) — a real portfolio figure in this domain is always a
#     decimal, a percentage, a multi-digit count, or a date, all of which still
#     must trace. A fabricated figure like "dropped 42%" or "beta of 1.9" is
#     unaffected: 42 is multi-digit and 1.9 carries a decimal.
_ALLOWED_NUMBERS = frozenset({"100", "0", "1", "2", "3"})

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_TICKER_RE = re.compile(r"\b[A-Z]{2,5}\b")


def _numbers(text: str) -> set[str]:
    """All numeric tokens (ints/decimals) in a string."""
    return set(_NUMBER_RE.findall(text))


def _tickers(text: str) -> set[str]:
    """Uppercase alpha tokens 2-5 chars — candidate stock/fund symbols."""
    return set(_TICKER_RE.findall(text))


def _input_corpus(grade: dict) -> str:
    """Everything the engine put in the grade payload, as one searchable string.

    Numbers and tickers may legitimately appear in the rephrased text only if
    they show up somewhere in here.
    """
    parts = [str(grade["score"]), grade["grade"], grade["interpretation"]]
    for comp in grade["components"].values():
        parts += [str(comp["penalty"]), str(comp["max_penalty"]), comp["reason"]]
    return " ".join(parts)


def _rephrased_text(enriched: dict) -> str:
    """The dynamic surface the model rephrased — the only text under the guard.

    Excludes the static ``meaning`` copy (see module docstring) and the numeric
    ``penalty``/``max_penalty`` fields, which the model does not author.
    """
    parts = [enriched.get("headline", ""), enriched.get("overview", "")]
    for c in enriched.get("components", []):
        parts.append(c.get("detail", ""))
    return " ".join(parts)


def is_valid(enriched: dict, grade: dict) -> bool:
    """True if every figure and ticker in ``enriched`` traces to ``grade``.

    ``enriched`` is the model's rephrased explanation (headline, overview,
    component details); ``grade`` is the ``risk_grade`` payload the facts were
    built from. Any untraceable number or ticker-shaped token fails the check,
    signalling the caller to fall back to the deterministic text.
    """
    corpus = _input_corpus(grade)
    text = _rephrased_text(enriched)

    input_numbers = _numbers(corpus) | _ALLOWED_NUMBERS
    for n in _numbers(text):
        if n not in input_numbers:
            return False

    input_tickers = _tickers(corpus) | _ALLOWED_ACRONYMS
    for t in _tickers(text):
        if t not in input_tickers:
            return False

    return True
