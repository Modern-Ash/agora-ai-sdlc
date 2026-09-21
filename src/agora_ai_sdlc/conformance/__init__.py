"""Public entry points for the bundled AI-SDLC conformance harness."""

from agora_ai_sdlc.conformance.compatibility import (
    FACTS_SCHEMA,
    STATUSES,
    CapabilityFact,
    CapabilityResult,
    ConformanceError,
    ConformanceReport,
    evaluate,
    evaluate_project,
    load_facts,
    parse_facts,
    render_human,
)
from agora_ai_sdlc.conformance.compatibility import RESULT_SCHEMA as COMPATIBILITY_RESULT_SCHEMA
from agora_ai_sdlc.conformance.self_test import RESULT_SCHEMA, run_self_test

__all__ = [
    "COMPATIBILITY_RESULT_SCHEMA",
    "FACTS_SCHEMA",
    "RESULT_SCHEMA",
    "STATUSES",
    "CapabilityFact",
    "CapabilityResult",
    "ConformanceError",
    "ConformanceReport",
    "evaluate",
    "evaluate_project",
    "load_facts",
    "parse_facts",
    "render_human",
    "run_self_test",
]
