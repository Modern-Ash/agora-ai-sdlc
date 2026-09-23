"""Shared classification for recoverable LLM/provider failures."""

from __future__ import annotations

RECOVERABLE_LLM_MARKERS = (
    "usage limit",
    "token limit",
    "tokens exhausted",
    "insufficient credits",
    "credit balance",
    "quota",
    "free usage exceeded",
    "rate limit",
    "too many requests",
    "invalid api key",
    "api key is missing",
    "authentication failed",
    "unauthorized",
    "forbidden",
    "provider not found",
    "model not found",
    "provider is not configured",
    "free model selection failed",
    "ollama pull failed",
    "cannot pull ollama model",
    "service temporarily overloaded",
    "service overloaded",
    "service unavailable",
    "temporarily unavailable",
    "server_error",
    "upstream error",
    "bad gateway",
    "gateway timeout",
    "connection reset",
    "connection aborted",
    "connection refused",
    "[502]",
    "[503]",
    "[504]",
)


def recoverable_llm_failure(text: str) -> bool:
    """Return whether a provider/runtime failure supports choosing another LLM/model."""

    normalized = text.casefold()
    return any(marker in normalized for marker in RECOVERABLE_LLM_MARKERS)
