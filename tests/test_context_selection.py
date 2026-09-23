import json
from pathlib import Path

from agora_ai_sdlc.artifacts import parse_artifact
from agora_ai_sdlc.context_graph import build_graph
from agora_ai_sdlc.context_selection import select_context_with_laya
from agora_ai_sdlc.decision_plane import DecisionAnswer, DecisionResult


def doc(kind, artifact_id, traces=(), body="body"):
    return (
        "---\n"
        'schema: "agora-ai-sdlc/artifact/v1"\n'
        f'kind: "{kind}"\nversion: 1\nid: "{artifact_id}"\nwork: "w"\nrevision: 1\n'
        f"traces-to: {json.dumps(list(traces))}\n"
        'required-sections: ["Section"]\n---\n'
        f"# {kind}\n\n## Section\n\n{body}\n"
    )


class RelevanceProvider:
    name = "laya"

    def decide(self, state, questions):
        artifact = state["candidate"]["id"]
        mapping = {
            "REQ-001": ("required", 0.98),
            "ARC-001": ("irrelevant", 0.97),
            "TST-001": ("irrelevant", 0.55),
        }
        value, confidence = mapping[artifact]
        return DecisionResult(
            provider="laya",
            answers={
                "relevance": DecisionAnswer(
                    question="relevance",
                    type="choice",
                    value=value,
                    confidence=confidence,
                    probabilities={value: confidence},
                )
            },
            latency_ms=5.0,
            model="typed-decisions",
        )


def graph():
    docs = []
    for path, text in [
        ("req.md", doc("requirements", "REQ-001")),
        ("arc.md", doc("architecture", "ARC-001", ["REQ-001"])),
        ("tst.md", doc("test-plan", "TST-001", ["REQ-001"])),
    ]:
        docs.append((Path(path), text, parse_artifact(text)))
    return build_graph(docs)


def test_laya_prunes_confident_irrelevant_context_and_keeps_uncertain_context():
    selection = select_context_with_laya(
        graph(),
        "REQ-001",
        provider=RelevanceProvider(),
        confidence_threshold=0.90,
    )

    selected = {item.id for item in selection.selected.items}
    assert "REQ-001" in selected
    assert "ARC-001" not in selected
    assert "TST-001" in selected  # fail open on low confidence
    assert selection.escalated == ("TST-001",)
    assert selection.metrics.context_tokens_saved > 0
    assert selection.metrics.decisions == 2
    assert selection.metrics.confident == 1
    assert selection.metrics.escalated == 1
