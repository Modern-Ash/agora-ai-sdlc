"""System-1 triage for deterministic verification failures."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from agora_ai_sdlc.decision_plane import (
    ConfidencePolicy,
    DecisionProvider,
    DecisionQuestion,
    evaluate_with_confidence,
)
from agora_ai_sdlc.verification import VerificationReport

FAILURE_QUESTION = DecisionQuestion(
    id="failure_class",
    type="choice",
    instructions=(
        "Classify the observed deterministic build/test failure. "
        "Do not claim the failure is fixed and do not infer lifecycle authority."
    ),
    criteria={
        "compile": "compiler, type-checker or symbol-resolution failure",
        "test": "test assertion or test-runner failure",
        "lint-format": "linting or formatting failure",
        "dependency": "missing dependency, import, module or package resolution failure",
        "build-config": "build configuration, manifest or build-script failure",
        "tool-unavailable": "required build/test/runtime tool is unavailable",
        "environment": "environment or runtime configuration prevents verification",
        "api-mismatch": "API, method, field or signature mismatch",
        "timeout-performance": "verification timed out or exposed a performance/resource problem",
        "security": "failure is security-sensitive or concerns trust/credentials/permissions",
        "unknown": "failure is multi-causal, architectural or cannot be classified safely",
    },
)

LOCAL_REPAIR_CLASSES = {
    "compile",
    "test",
    "lint-format",
    "dependency",
    "build-config",
    "tool-unavailable",
    "environment",
    "api-mismatch",
}


@dataclass(frozen=True)
class FailureTriage:
    failure_class: str
    confidence: float
    escalated: bool
    route: str
    diagnostic_digest: str
    provider: str
    model: str | None
    latency_ms: float


def _diagnostic(report: VerificationReport, max_chars: int = 6000) -> str:
    failures = []
    for command in report.commands:
        if command.status == "passed":
            continue
        output = command.stderr or command.stdout
        failures.append(
            {
                "command": command.command,
                "status": command.status,
                "exit_code": command.exit_code,
                "diagnostic": " ".join(output.split())[-2000:],
            }
        )
    text = json.dumps(
        {
            "work": report.work,
            "head": report.head,
            "failures": failures[:4],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return text[:max_chars]


def triage_verification_failure(
    report: VerificationReport,
    *,
    provider: DecisionProvider,
    confidence_threshold: float = 0.90,
) -> FailureTriage | None:
    """Classify a failed executed report; successful/planned reports need no triage."""

    if not report.executed or report.all_executed_commands_passed is not False:
        return None

    diagnostic = _diagnostic(report)
    digest = "sha256:" + hashlib.sha256(diagnostic.encode()).hexdigest()
    state = {
        "diagnostic": diagnostic,
        "acceptance_criteria": [item.criterion for item in report.acceptance_coverage],
    }
    evaluation = evaluate_with_confidence(
        provider,
        state,
        (FAILURE_QUESTION,),
        policy=ConfidencePolicy(confidence_threshold),
    )
    answer = evaluation.result.answers["failure_class"]
    failure_class = str(answer.value)
    escalated = bool(evaluation.escalated)
    route = (
        "paid-advisory"
        if escalated or failure_class in {"unknown", "security", "timeout-performance"}
        else "local-repair"
        if failure_class in LOCAL_REPAIR_CLASSES
        else "paid-advisory"
    )
    return FailureTriage(
        failure_class=failure_class,
        confidence=float(answer.confidence),
        escalated=escalated,
        route=route,
        diagnostic_digest=digest,
        provider=evaluation.result.provider,
        model=evaluation.result.model,
        latency_ms=evaluation.result.latency_ms or 0.0,
    )
