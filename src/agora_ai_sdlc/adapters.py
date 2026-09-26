"""Default RuntimeAdapter registry; concrete adapters register here, never in lifecycle code."""

from __future__ import annotations

from agora_ai_sdlc.claude_code_adapter import ClaudeCodeAdapter
from agora_ai_sdlc.codex_adapter import CodexAdapter
from agora_ai_sdlc.runtime_adapter import AdapterRegistry


def default_registry(*, claude_options: dict | None = None, codex_options: dict | None = None) -> AdapterRegistry:
    registry = AdapterRegistry()
    registry.register(ClaudeCodeAdapter(**(claude_options or {})))
    registry.register(CodexAdapter(**(codex_options or {})))
    return registry
