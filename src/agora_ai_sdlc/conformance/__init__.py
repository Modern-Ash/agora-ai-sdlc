"""Public entry points for the bundled AI-SDLC conformance harness."""

from agora_ai_sdlc.conformance.aws_original import RULES_SCHEMA as AWS_ORIGINAL_RULES_SCHEMA
from agora_ai_sdlc.conformance.aws_original import AwsOriginalRuleError, derive_additive_governance
from agora_ai_sdlc.conformance.aws_original import derive_facts as derive_aws_original_facts
from agora_ai_sdlc.conformance.aws_original import load_rules as load_aws_original_rules
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
    "AWS_ORIGINAL_RULES_SCHEMA",
    "COMPATIBILITY_RESULT_SCHEMA",
    "FACTS_SCHEMA",
    "RESULT_SCHEMA",
    "STATUSES",
    "AwsOriginalRuleError",
    "CapabilityFact",
    "CapabilityResult",
    "ConformanceError",
    "ConformanceReport",
    "derive_additive_governance",
    "derive_aws_original_facts",
    "evaluate",
    "evaluate_project",
    "load_aws_original_rules",
    "load_facts",
    "parse_facts",
    "render_human",
    "run_self_test",
]
