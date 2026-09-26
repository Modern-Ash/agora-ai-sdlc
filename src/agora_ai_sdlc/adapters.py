"""Default RuntimeAdapter registry; concrete adapters register here, never in lifecycle code."""

from __future__ import annotations

from agora_ai_sdlc.claude_code_adapter import ClaudeCodeAdapter
from agora_ai_sdlc.runtime_adapter import AdapterRegistry


def default_registry(**claude_options) -> AdapterRegistry:
    registry = AdapterRegistry()
    registry.register(ClaudeCodeAdapter(**claude_options))
    return registry
