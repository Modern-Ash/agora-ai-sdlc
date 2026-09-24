"""Free, local System-1 provider backed by the Apache-2.0 Laya project."""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from typing import Any

from agora_ai_sdlc.decision_plane import (
    DecisionAnswer,
    DecisionPlaneError,
    DecisionQuestion,
    DecisionResult,
)


class LayaUnavailable(RuntimeError):
    """Raised when the optional Laya runtime is not installed or cannot load."""


class LayaDecisionProvider:
    name = "laya"

    def __init__(self, *, router: Any | None = None, model: str | None = None) -> None:
        self._router = router
        self.model = model or os.environ.get("AGORA_LAYA_MODEL", "typed-decisions")

    def _get_router(self) -> Any:
        if self._router is not None:
            return self._router
        try:
            from laya import Router
        except ImportError as error:
            raise LayaUnavailable(
                'Laya decision capability is not installed. Install the full distribution with: pip install "agora-ai-sdlc[full]"'
            ) from error
        try:
            self._router = Router()
        except Exception as error:
            raise LayaUnavailable(f"unable to initialize Laya Router: {error}") from error
        return self._router

    @staticmethod
    def _normalize(question: DecisionQuestion, raw: Mapping[str, Any]) -> DecisionAnswer:
        probabilities = {
            str(key): float(value)
            for key, value in (raw.get("probabilities") or {}).items()
            if isinstance(value, (int, float))
        }

        if question.type == "choice":
            value = raw.get("choice")
            if not isinstance(value, str):
                raise DecisionPlaneError("decision.laya_shape", f"{question.id}: missing choice")
            confidence = raw.get("confidence")
            if not isinstance(confidence, (int, float)):
                confidence = probabilities.get(value, 0.0)
        elif question.type == "noul":
            value = raw.get("noul")
            if not isinstance(value, (int, float)):
                raise DecisionPlaneError("decision.laya_shape", f"{question.id}: missing noul score")
            value = float(value)
            confidence = raw.get("confidence")
            if not isinstance(confidence, (int, float)):
                confidence = max(value, 1.0 - value)
        else:
            value = raw.get("score")
            if not isinstance(value, (int, float, str)):
                raise DecisionPlaneError("decision.laya_shape", f"{question.id}: missing score")
            confidence = raw.get("confidence")
            if not isinstance(confidence, (int, float)):
                confidence = max(probabilities.values(), default=0.0)

        return DecisionAnswer(
            question=question.id,
            type=question.type,
            value=value,
            confidence=float(confidence),
            probabilities=probabilities,
            raw=dict(raw),
        )

    def decide_many(
        self,
        requests: tuple[tuple[Mapping[str, Any], tuple[DecisionQuestion, ...]], ...],
    ) -> tuple[DecisionResult, ...]:
        """Evaluate heterogeneous typed decisions with one routed Laya batch when available."""

        if not requests:
            return ()
        router = self._get_router()
        payloads = [
            {
                "state": dict(state),
                "questions": {question.id: question.as_laya() for question in questions},
                "model": self.model,
            }
            for state, questions in requests
        ]
        started = time.perf_counter()
        try:
            if hasattr(router, "predict_batch"):
                raw_results = router.predict_batch(payloads)
            else:
                raw_results = [router.predict(item["state"], item["questions"], model=self.model) for item in payloads]
        except TypeError:
            raw_results = [router.predict(item["state"], item["questions"]) for item in payloads]
        except Exception as error:
            raise DecisionPlaneError("decision.laya_predict_batch", str(error)) from error
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        if not isinstance(raw_results, (list, tuple)) or len(raw_results) != len(requests):
            raise DecisionPlaneError("decision.laya_batch_shape", "Laya returned an invalid batch response")

        results: list[DecisionResult] = []
        per_request_latency = elapsed_ms / max(1, len(requests))
        for raw, (_, questions) in zip(raw_results, requests):
            if not isinstance(raw, Mapping) or not isinstance(raw.get("answers"), Mapping):
                raise DecisionPlaneError("decision.laya_batch_shape", "Laya batch item has invalid response shape")
            raw_answers = raw["answers"]
            answers = {
                question.id: self._normalize(question, raw_answers[question.id])
                for question in questions
                if question.id in raw_answers
            }
            routing = raw.get("routing")
            model = self.model
            if isinstance(routing, Mapping) and isinstance(routing.get("model"), str):
                model = routing["model"]
            results.append(
                DecisionResult(
                    provider=self.name,
                    answers=answers,
                    latency_ms=per_request_latency,
                    model=model,
                    metadata={"routing": dict(routing) if isinstance(routing, Mapping) else {}, "batched": True},
                )
            )
        return tuple(results)

    def decide(
        self,
        state: Mapping[str, Any],
        questions: tuple[DecisionQuestion, ...],
    ) -> DecisionResult:
        if not state:
            raise DecisionPlaneError("decision.state", "state must not be empty")
        if not questions:
            raise DecisionPlaneError("decision.questions", "at least one question is required")

        payload = {question.id: question.as_laya() for question in questions}
        router = self._get_router()
        started = time.perf_counter()
        try:
            raw = router.predict(dict(state), payload, model=self.model)
        except TypeError:
            # Test doubles and older compatible Router implementations may not expose model=.
            raw = router.predict(dict(state), payload)
        except Exception as error:
            raise DecisionPlaneError("decision.laya_predict", str(error)) from error
        latency_ms = (time.perf_counter() - started) * 1000.0

        if not isinstance(raw, Mapping) or not isinstance(raw.get("answers"), Mapping):
            raise DecisionPlaneError("decision.laya_shape", "Laya returned an invalid response")
        raw_answers = raw["answers"]
        answers = {
            question.id: self._normalize(question, raw_answers[question.id])
            for question in questions
            if question.id in raw_answers
        }
        routing = raw.get("routing")
        model = self.model
        if isinstance(routing, Mapping) and isinstance(routing.get("model"), str):
            model = routing["model"]
        return DecisionResult(
            provider=self.name,
            answers=answers,
            latency_ms=latency_ms,
            model=model,
            metadata={"routing": dict(routing) if isinstance(routing, Mapping) else {}},
        )
