"""Metrics for measuring whether the decision plane actually saves LLM work."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class DecisionMetrics:
    decisions: int = 0
    confident: int = 0
    escalated: int = 0
    laya_latency_ms: float = 0.0
    candidate_context_tokens: int = 0
    selected_context_tokens: int = 0
    avoided_llm_calls: int = 0

    @property
    def context_tokens_saved(self) -> int:
        return max(0, self.candidate_context_tokens - self.selected_context_tokens)

    @property
    def context_reduction_ratio(self) -> float:
        if self.candidate_context_tokens <= 0:
            return 0.0
        return self.context_tokens_saved / self.candidate_context_tokens

    def snapshot(self) -> dict:
        data = asdict(self)
        data["context_tokens_saved"] = self.context_tokens_saved
        data["context_reduction_ratio"] = round(self.context_reduction_ratio, 6)
        return data
