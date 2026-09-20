"""Public entry points for the bundled AI-SDLC conformance harness."""

from agora_ai_sdlc.conformance.self_test import RESULT_SCHEMA, run_self_test

__all__ = ["RESULT_SCHEMA", "run_self_test"]
