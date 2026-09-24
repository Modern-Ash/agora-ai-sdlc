"""Laya-assisted pruning of deterministic execution context.

Agora first computes candidate paths deterministically. Laya may only remove
candidates; changed/dirty files and low-confidence decisions fail open and stay.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from agora_ai_sdlc.context_graph import estimate_tokens
from agora_ai_sdlc.decision_plane import ConfidencePolicy, DecisionProvider, DecisionQuestion, evaluate_with_confidence
from agora_ai_sdlc.execution_bundle import ExecutionBundle

FILE_RELEVANCE = DecisionQuestion(
    id="relevance",
    type="choice",
    instructions=(
        "Classify whether this repository file is needed for the current implementation or verification task. "
        "Use irrelevant only when safely excluding the file cannot affect the requested outcome."
    ),
    criteria={
        "required": "directly needed to implement, verify, or understand the requested change",
        "useful": "supporting context likely to improve correctness",
        "irrelevant": "not needed for this bounded task",
    },
)


@dataclass(frozen=True)
class ExecutionContextSelection:
    candidate_paths: tuple[str, ...]
    selected_paths: tuple[str, ...]
    protected_paths: tuple[str, ...]
    escalated_paths: tuple[str, ...]
    classifications: dict[str, str]
    confidences: dict[str, float]
    candidate_tokens: int
    selected_tokens: int
    latency_ms: float

    @property
    def saved_tokens(self) -> int:
        return max(0, self.candidate_tokens - self.selected_tokens)

    @property
    def reduction_ratio(self) -> float:
        if self.candidate_tokens <= 0:
            return 0.0
        return self.saved_tokens / self.candidate_tokens

    def snapshot(self) -> dict:
        data = asdict(self)
        data["saved_tokens"] = self.saved_tokens
        data["reduction_ratio"] = round(self.reduction_ratio, 6)
        return data


def _read(root: Path, relative: str, max_chars: int) -> tuple[str, int]:
    path = root / relative
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return "", 0
    tokens = estimate_tokens(text)
    if max_chars > 0 and len(text) > max_chars:
        head = max_chars // 2
        tail = max_chars - head
        text = text[:head] + "\n...[bounded]...\n" + text[-tail:]
    return text, tokens


def select_execution_context(
    root: Path,
    bundle: ExecutionBundle,
    *,
    provider: DecisionProvider,
    confidence_threshold: float = 0.90,
    max_chars_per_file: int = 3200,
) -> ExecutionContextSelection:
    """Prune only deterministic related-path candidates; never add new paths."""

    root = root.resolve()
    candidates = tuple(dict.fromkeys((*bundle.changed_paths, *bundle.dirty_paths, *bundle.related_paths)))
    protected = set(bundle.changed_paths) | set(bundle.dirty_paths)
    selected = set(protected)
    escalated = []
    classifications: dict[str, str] = {}
    confidences: dict[str, float] = {}
    candidate_tokens = 0
    selected_tokens = 0
    latency_ms = 0.0
    tokens_by_path: dict[str, int] = {}

    for relative in candidates:
        text, tokens = _read(root, relative, max_chars_per_file)
        tokens_by_path[relative] = tokens
        candidate_tokens += tokens

        if relative in protected:
            classifications[relative] = "required"
            confidences[relative] = 1.0
            continue

        state = {
            "objective": bundle.objective or "",
            "acceptance_criteria": list(bundle.acceptance_criteria),
            "stage": bundle.stage,
            "risks": list(bundle.risks),
            "candidate": {
                "path": relative,
                "content": text,
            },
        }
        evaluation = evaluate_with_confidence(
            provider,
            state,
            (FILE_RELEVANCE,),
            policy=ConfidencePolicy(confidence_threshold),
        )
        answer = evaluation.result.answers["relevance"]
        classifications[relative] = str(answer.value)
        confidences[relative] = answer.confidence
        latency_ms += evaluation.result.latency_ms or 0.0

        if evaluation.escalated:
            selected.add(relative)
            escalated.append(relative)
        elif answer.value in {"required", "useful"}:
            selected.add(relative)

    ordered_selected = tuple(path for path in candidates if path in selected)
    selected_tokens = sum(tokens_by_path.get(path, 0) for path in ordered_selected)
    return ExecutionContextSelection(
        candidate_paths=candidates,
        selected_paths=ordered_selected,
        protected_paths=tuple(path for path in candidates if path in protected),
        escalated_paths=tuple(escalated),
        classifications=classifications,
        confidences=confidences,
        candidate_tokens=candidate_tokens,
        selected_tokens=selected_tokens,
        latency_ms=latency_ms,
    )


def persist_execution_context(root: Path, work: str, selection: ExecutionContextSelection) -> Path:
    target = root / ".agora" / "ai-sdlc" / "bundles" / work / "LEAN_EXECUTION_CONTEXT.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(selection.snapshot(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
