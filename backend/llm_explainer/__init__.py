"""Structured LLM explainer layer.

PR1 ships `templates.py` — deterministic, pure-Python explanations of the
portfolio risk grade. Later PRs add the LLM enrichment (`client.py`,
`context.py`, `validator.py`, `cache.py`) that rephrases the same structured
data and falls back to these templates on any failure.
"""
