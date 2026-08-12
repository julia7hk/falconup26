"""Thin Groq wrapper for the risk-grade explainer (M8 PR2).

The single I/O boundary of the LLM layer — the only module here that touches the
network or an LLM SDK. Groq exposes an OpenAI-compatible API, so we drive it with
the `openai` SDK pointed at Groq's base URL. Everything flaky and external is
quarantined in one function: no API key, import failure, timeout, or malformed
output all collapse to the same signal — ``None`` — which tells the caller to
serve the deterministic PR1 text. The layer degrades to "no LLM" silently and by
design; a missing key is a supported configuration, not an error.

Deliberately *not* responsible for validation (``validator.py``) or for merging
the rephrased fields back over the baseline (``__init__.explain``). This returns
only the raw parsed LLM fields.
"""

from __future__ import annotations

import logging
import os

from pydantic import BaseModel, ValidationError

from .context import build_user_content
from .prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Groq's OpenAI-compatible endpoint.
_BASE_URL = "https://api.groq.com/openai/v1"
# Cheap, fast, free-tier model by design: the model is a rephraser guarded by the
# validator + a deterministic fallback, so raw intelligence barely matters here.
# Only reach for a larger model if rephrasing quality actually disappoints.
_MODEL = "llama-3.3-70b-versatile"
_MAX_TOKENS = 2048
# Keep the request snappy — this sits in the /risk/explain request path, and a
# slow model call should fall back to the instant deterministic text, not hang.
_TIMEOUT_SECONDS = 20.0
_MAX_RETRIES = 1


class _Component(BaseModel):
    key: str
    detail: str


class LLMExplanation(BaseModel):
    """The structured shape the model must return — the fields it may rephrase."""

    headline: str
    overview: str
    components: list[_Component]


def generate(explanation: dict) -> dict | None:
    """Ask the model to rephrase the deterministic explanation.

    ``explanation`` is the PR1 ``templates.explain_grade`` output. Returns the
    parsed LLM fields as a dict (``{headline, overview, components:[{key,
    detail}]}``) on success, or ``None`` on any failure — no key configured, SDK
    unavailable, timeout, network error, empty completion, or output that didn't
    parse to the schema. The caller treats ``None`` as "fall back to PR1".
    """
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        # Expected, supported configuration — LLM enrichment is simply off.
        return None

    try:
        from openai import OpenAI  # lazy: a missing SDK must not break app import
    except ImportError:
        logger.warning("openai SDK not installed; serving deterministic explanation")
        return None

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=_BASE_URL,
            timeout=_TIMEOUT_SECONDS,
            max_retries=_MAX_RETRIES,
        )
        response = client.chat.completions.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            # Groq's JSON mode: the model must return a single JSON object. The
            # prompt describes the exact shape; pydantic re-checks it below.
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_content(explanation)},
            ],
        )
    except Exception as exc:  # timeout, rate limit, network, API error, etc.
        logger.warning("LLM explanation failed (%s); serving deterministic text", exc)
        return None

    content = response.choices[0].message.content if response.choices else None
    if not content:  # empty completion or hit the token ceiling before any text
        logger.warning("LLM returned no content; serving deterministic text")
        return None

    try:
        parsed = LLMExplanation.model_validate_json(content)
    except ValidationError:
        logger.warning("LLM output did not parse to schema; serving deterministic text")
        return None

    return parsed.model_dump()
