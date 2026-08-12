"""Structured LLM explainer layer.

``templates.py`` (M8 PR1) is the deterministic, pure-Python baseline: it turns a
``risk_grade`` payload into plain-English explanations with no I/O. PR2 adds an
LLM that *rephrases* that same structured text into warmer, beginner-friendly
prose — it never computes. The pieces:

- ``context.py`` assembles the baseline explanation into the model's input
  (the experimentation seam),
- ``prompt.py`` holds the single versioned prompt,
- ``client.py`` is the one I/O boundary (Groq call; returns ``None`` on any
  failure — no key, timeout, bad output),
- ``validator.py`` rejects any rephrasing that introduces a number or ticker the
  engine didn't produce.

``explain`` ties them together: LLM-enriched text when it's available *and*
valid, the deterministic PR1 text otherwise — seamlessly, with a ``source``
marker so callers/telemetry can tell which path served the response.
"""

from __future__ import annotations

import logging

from . import client, validator
from .templates import DISCLAIMER, explain_grade

logger = logging.getLogger(__name__)

__all__ = ["explain", "explain_grade", "DISCLAIMER"]


def _merge(baseline: dict, enriched: dict) -> dict:
    """Overlay the model's rephrased fields onto the deterministic payload.

    Only the dynamic prose (``headline``, ``overview``, each component
    ``detail``) is replaced; ``label``/``meaning``/``penalty``/``max_penalty``/
    ``severity`` stay exactly as the engine produced them. Any field or
    component the model omitted keeps its deterministic value, so a partial LLM
    response still yields a complete, coherent explanation.
    """
    llm_details = {c.get("key"): c.get("detail", "") for c in enriched.get("components", [])}
    components = [
        {**c, "detail": llm_details.get(c["key"]) or c["detail"]}
        for c in baseline["components"]
    ]
    return {
        **baseline,
        "headline": enriched.get("headline") or baseline["headline"],
        "overview": enriched.get("overview") or baseline["overview"],
        "components": components,
    }


def explain(grade: dict) -> dict:
    """Best-available explanation of a ``risk_grade`` payload.

    Returns the same presentation shape as ``explain_grade`` plus a ``source``
    field (``"llm"`` or ``"deterministic"``). The LLM path is taken only when a
    rephrasing comes back *and* passes the traceability validator; otherwise the
    deterministic PR1 text is returned unchanged. Blocking (it may make a network
    call) — call it off the event loop (e.g. ``asyncio.to_thread``).
    """
    baseline = explain_grade(grade)
    raw = client.generate(baseline)
    if raw is not None:
        merged = _merge(baseline, raw)
        if validator.is_valid(merged, grade):
            return {**merged, "source": "llm"}
        logger.warning("LLM explanation failed validation; serving deterministic text")
    return {**baseline, "source": "deterministic"}
