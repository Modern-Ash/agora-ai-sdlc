"""Reusable non-authoritative decision session for one governed Work snapshot."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_decisions import DecisionEvaluation, advise_execution
from agora_ai_sdlc.execution_policy import ExecutionPolicy, execution_policy_for
from agora_ai_sdlc import execution_requirements
from agora_ai_sdlc.laya_provider import LayaDecisionProvider


QUESTION_SCHEMA = "execution-decisions/v2"


def bundle_digest(bundle: ExecutionBundle) -> str:
    """Digest only bounded advisory inputs; never authority or provider output."""

    body = {
        "schema": bundle.schema,
        "swarm": bundle.swarm,
        "work": bundle.work,
        "stage": bundle.stage,
        "objective": bundle.objective,
        "acceptance_criteria": list(bundle.acceptance_criteria),
        "changed_paths": list(bundle.changed_paths),
        "dirty_paths": list(bundle.dirty_paths),
        "related_paths": list(bundle.related_paths),
        "languages": list(bundle.languages),
        "build_systems": list(bundle.build_systems),
        "verification_commands": list(bundle.verification_commands),
        "risks": list(bundle.risks),
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass
class FlowDecisionSession:
    """Cache advisory Laya projections for one unchanged bounded Work input."""

    snapshot_token: str | None = None
    confidence_threshold: float = 0.90
    provider: Any = field(default_factory=LayaDecisionProvider)
    _digest: str | None = field(default=None, init=False, repr=False)
    _evaluation: DecisionEvaluation | None = field(default=None, init=False, repr=False)
    _requirements: execution_requirements.ExecutionRequirements | None = field(default=None, init=False, repr=False)
    _policy: ExecutionPolicy | None = field(default=None, init=False, repr=False)
    calls: int = field(default=0, init=False)
    hits: int = field(default=0, init=False)

    def _key(self, bundle: ExecutionBundle) -> str:
        payload = {
            "snapshot_token": self.snapshot_token,
            "bundle_digest": bundle_digest(bundle),
            "provider": getattr(self.provider, "name", type(self.provider).__name__),
            "model": getattr(self.provider, "model", None),
            "question_schema": QUESTION_SCHEMA,
            "confidence_threshold": self.confidence_threshold,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    def evaluation(self, bundle: ExecutionBundle) -> DecisionEvaluation:
        key = self._key(bundle)
        if self._digest == key and self._evaluation is not None:
            self.hits += 1
            return self._evaluation

        evaluated = advise_execution(
            bundle,
            provider=self.provider,
            confidence_threshold=self.confidence_threshold,
        )
        self.calls += 1
        self._digest = key
        self._evaluation = evaluated
        self._requirements = None
        self._policy = None
        return evaluated

    def requirements(self, bundle: ExecutionBundle) -> execution_requirements.ExecutionRequirements:
        if self._requirements is not None and self._digest == self._key(bundle):
            self.hits += 1
            return self._requirements
        self._requirements = execution_requirements.project_requirements(bundle, self.evaluation(bundle))
        return self._requirements

    def policy(self, bundle: ExecutionBundle) -> ExecutionPolicy:
        if self._policy is not None and self._digest == self._key(bundle):
            self.hits += 1
            return self._policy
        self._policy = execution_policy_for(self.requirements(bundle))
        return self._policy

    def diagnostics(self, bundle: ExecutionBundle) -> dict[str, Any]:
        return {
            "schema": "agora-ai-sdlc/flow-decision-session/v1",
            "cache_key": self._key(bundle),
            "snapshot_token": self.snapshot_token,
            "bundle_digest": bundle_digest(bundle),
            "provider": getattr(self.provider, "name", type(self.provider).__name__),
            "model": getattr(self.provider, "model", None),
            "question_schema": QUESTION_SCHEMA,
            "confidence_threshold": self.confidence_threshold,
            "calls": self.calls,
            "hits": self.hits,
            "cached": self._digest == self._key(bundle) and self._evaluation is not None,
        }
