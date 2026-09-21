import json
from pathlib import Path

import pytest

from agora_ai_sdlc.artifacts import parse_artifact
from agora_ai_sdlc.cli import main
from agora_ai_sdlc.context_graph import (
    ContextError,
    build_graph,
    context_bundle,
    find_cycles,
    graph_from_directory,
)
from agora_ai_sdlc.semantic_elevation import SemanticElevationError, validate_semantic_elevation

ROOT = Path(__file__).parent.parent
BOLTS = (ROOT / "tests" / "fixtures" / "bolts" / "parallel.md").read_text(encoding="utf-8")


def doc(kind, artifact_id, traces=(), work="w", body="body"):
    return (
        "---\n"
        'schema: "agora-ai-sdlc/artifact/v1"\n'
        f'kind: "{kind}"\nversion: 1\nid: "{artifact_id}"\nwork: "{work}"\nrevision: 1\n'
        f"traces-to: {json.dumps(list(traces))}\n"
        'required-sections: ["Section"]\n---\n'
        f"# {kind}\n\n## Section\n\n{body}\n"
    )


def bolt_plan() -> str:
    text = BOLTS.replace('traces-to: ["UOW-001", "PLN-001"]', 'traces-to: ["UOW-001"]').replace(
        'plan: "PLN-001"', "plan: null"
    )
    return text


def corpus(tmp_path: Path, extra: dict[str, str] | None = None) -> Path:
    files = {
        "int1.md": doc("intent", "INT-001"),
        "uow1.md": doc("unit-of-work", "UOW-001", ["INT-001"]),
        "uow2.md": doc("unit-of-work", "UOW-002", ["INT-001"]),
        "req1.md": doc("requirements", "REQ-001", ["UOW-001"]),
        "req2.md": doc("requirements", "REQ-002", ["UOW-002"]),
        "arc1.md": doc("architecture", "ARC-001", ["REQ-001"]),
        "imp1.md": doc("implementation-plan", "IMP-001", ["ARC-001"]),
        "blp1.md": bolt_plan(),
        "int9.md": doc("intent", "INT-009"),
        "uow9.md": doc("unit-of-work", "UOW-009", ["INT-009"]),
        "README.md": "# not an artifact\n",
        **(extra or {}),
    }
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return tmp_path


def ids(bundle):
    return [item.id for item in bundle.items]


def test_unit_context_is_scoped_ordered_and_excludes_unrelated(tmp_path):
    graph = graph_from_directory(corpus(tmp_path))
    bundle = context_bundle(graph, "UOW-001")

    assert ids(bundle) == [
        "UOW-001",
        "INT-001",
        "REQ-001",
        "BLP-001",
        "ARC-001",
        "BLP-001/api",
        "BLP-001/integrate",
        "BLP-001/schema",
        "BLP-001/ui",
        "IMP-001",
    ]
    assert not {"UOW-002", "REQ-002", "INT-009", "UOW-009"} & set(ids(bundle))
    assert context_bundle(graph, "UOW-001").snapshot() == bundle.snapshot()


def test_backward_and_forward_directions_are_independent(tmp_path):
    graph = graph_from_directory(corpus(tmp_path))
    assert ids(context_bundle(graph, "REQ-001", direction="backward")) == ["REQ-001", "UOW-001", "INT-001"]
    forward = ids(context_bundle(graph, "REQ-001", direction="forward"))
    assert forward[0] == "REQ-001" and "ARC-001" in forward and "INT-001" not in forward


def test_bolt_context_links_plan_unit_dependencies_and_produced_artifacts(tmp_path):
    graph = graph_from_directory(corpus(tmp_path))
    bundle = context_bundle(graph, "BLP-001/schema")
    assert ids(bundle)[:2] == ["BLP-001/schema", "BLP-001"]
    assert "IMP-001" in ids(bundle)  # produced by the bolt
    # backward from the artifact reaches the producing bolt, so Unit -> Bolt -> artifact is navigable
    assert "BLP-001/schema" in ids(context_bundle(graph, "IMP-001", direction="backward"))
    api = ids(context_bundle(graph, "BLP-001/api", direction="backward"))
    assert "BLP-001/schema" in api and "BLP-001/ui" not in api


def test_depth_and_token_budget_select_deterministically(tmp_path):
    graph = graph_from_directory(corpus(tmp_path))
    assert ids(context_bundle(graph, "UOW-001", max_depth=1, direction="backward")) == ["UOW-001", "INT-001"]

    full = context_bundle(graph, "UOW-001")
    budget = full.items[0].tokens + full.items[1].tokens
    small = context_bundle(graph, "UOW-001", max_tokens=budget)
    assert ids(small) == ["UOW-001", "INT-001"]
    assert small.total_tokens <= budget
    assert set(small.omitted) == set(ids(full)) - set(ids(small))
    tiny = context_bundle(graph, "UOW-001", max_tokens=1)
    assert ids(tiny) == ["UOW-001"]  # root is always kept


def test_dangling_links_are_reported_and_strict_fails(tmp_path):
    graph = graph_from_directory(corpus(tmp_path, {"req2.md": doc("requirements", "REQ-002", ["UOW-404"])}))
    bundle = context_bundle(graph, "REQ-002")
    assert bundle.dangling == (("REQ-002", "UOW-404"),)
    assert ids(bundle) == ["REQ-002"]
    with pytest.raises(ContextError) as exc:
        context_bundle(graph, "REQ-002", strict=True)
    assert exc.value.code == "context.dangling"
    assert context_bundle(graph, "UOW-001").dangling == ()  # unrelated dangling link not reported


def test_cycles_terminate_and_are_reported(tmp_path):
    extra = {
        "a.md": doc("clarification", "CLR-001", ["CLR-002"]),
        "b.md": doc("clarification", "CLR-002", ["CLR-001"]),
        "self.md": doc("clarification", "CLR-003", ["CLR-003"]),
    }
    graph = graph_from_directory(corpus(tmp_path, extra))
    assert find_cycles(graph) == (("CLR-001", "CLR-002"), ("CLR-003",))
    bundle = context_bundle(graph, "CLR-001")
    assert ids(bundle) == ["CLR-001", "CLR-002"]
    assert bundle.cycles == (("CLR-001", "CLR-002"),)
    with pytest.raises(ContextError) as exc:
        context_bundle(graph, "CLR-001", strict=True)
    assert exc.value.code == "context.cycle"
    assert context_bundle(graph, "UOW-001").cycles == ()


def test_errors_are_stable(tmp_path):
    graph = graph_from_directory(corpus(tmp_path))
    for kwargs, code in [
        ({"root": "NOPE-001"}, "context.unknown_root"),
        ({"root": "UOW-001", "direction": "sideways"}, "context.direction"),
        ({"root": "UOW-001", "max_tokens": 0}, "context.budget"),
        ({"root": "UOW-001", "max_depth": -1}, "context.depth"),
    ]:
        with pytest.raises(ContextError) as exc:
            context_bundle(graph, **kwargs)
        assert exc.value.code == code


def test_duplicate_ids_and_invalid_artifacts_fail_closed(tmp_path):
    with pytest.raises(ContextError) as exc:
        graph_from_directory(corpus(tmp_path, {"dup.md": doc("intent", "INT-001")}))
    assert exc.value.code == "context.duplicate_id"
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "x.md").write_text(doc("intent", "BAD"), encoding="utf-8")
    with pytest.raises(ContextError) as exc:
        graph_from_directory(broken)
    assert exc.value.code == "context.artifact"


def test_context_cli_json_and_content(tmp_path, capsys):
    root = corpus(tmp_path)
    assert main(["context", str(root), "UOW-001", "--direction", "backward", "--json", "--content"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [item["id"] for item in payload["items"]] == ["UOW-001", "INT-001"]
    assert "unit-of-work" in payload["text"]["UOW-001"]

    assert main(["context", str(root), "UOW-001", "--max-tokens", "1"]) == 0
    assert "omitted (budget)" in capsys.readouterr().out
    assert main(["context", str(root), "NOPE-001"]) == 2
    assert "context.unknown_root" in capsys.readouterr().err


def brownfield(tmp_path: Path, skip: str | None = None, work="brownfield") -> Path:
    files = {
        "lgi.md": doc("legacy-inventory", "LGI-001", work=work),
        "dpm.md": doc("dependency-map", "DPM-001", ["LGI-001"], work=work),
        "chr.md": doc("characterization", "CHR-001", ["LGI-001"], work=work),
        "ssm.md": doc("static-system-model", "SSM-001", ["LGI-001", "DPM-001"], work=work),
        "dsm.md": doc("dynamic-system-model", "DSM-001", ["SSM-001", "CHR-001"], work=work),
    }
    files.pop(skip, None)
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return tmp_path


def models(root: Path):
    from agora_ai_sdlc.context_graph import load_artifacts

    return [artifact for _, _, artifact in load_artifacts(root)]


def test_system_model_artifacts_join_the_trace_graph(tmp_path):
    graph = graph_from_directory(brownfield(tmp_path))
    assert ids(context_bundle(graph, "DSM-001", direction="backward")) == [
        "DSM-001",
        "SSM-001",
        "CHR-001",
        "LGI-001",
        "DPM-001",
    ]


def test_semantic_elevation_accepts_linked_models(tmp_path):
    assert validate_semantic_elevation(models(brownfield(tmp_path)), "brownfield") == ("SSM-001", "DSM-001")


@pytest.mark.parametrize(
    ("skip", "code"),
    [("ssm.md", "elevation.static_missing"), ("dsm.md", "elevation.dynamic_missing")],
)
def test_semantic_elevation_requires_both_models(tmp_path, skip, code):
    with pytest.raises(SemanticElevationError) as exc:
        validate_semantic_elevation(models(brownfield(tmp_path, skip=skip)), "brownfield")
    assert exc.value.code == code


def test_semantic_elevation_is_scoped_to_the_work(tmp_path):
    with pytest.raises(SemanticElevationError) as exc:
        validate_semantic_elevation(models(brownfield(tmp_path)), "other-work")
    assert exc.value.code == "elevation.static_missing"


def test_semantic_elevation_requires_links(tmp_path):
    root = brownfield(tmp_path)
    (root / "dsm.md").write_text(doc("dynamic-system-model", "DSM-001", ["CHR-001"], work="brownfield"))
    with pytest.raises(SemanticElevationError) as exc:
        validate_semantic_elevation(models(root), "brownfield")
    assert exc.value.code == "elevation.dynamic_unlinked"
    (root / "ssm.md").write_text(doc("static-system-model", "SSM-001", ["DPM-001"], work="brownfield"))
    (root / "dpm.md").write_text(doc("dependency-map", "DPM-001", ["LGI-001"], work="brownfield"))
    (root / "dsm.md").write_text(doc("dynamic-system-model", "DSM-001", ["SSM-001"], work="brownfield"))
    assert validate_semantic_elevation(models(root), "brownfield")


def test_plan_validate_enforces_elevation_only_for_pathways_that_require_it(tmp_path, capsys):
    plan = str(ROOT / "tests" / "fixtures" / "pathways" / "brownfield.md")
    args = ["plan-validate", plan, "--pathway", "brownfield", "--artifacts"]

    ok = tmp_path / "ok"
    ok.mkdir()
    assert main([*args, str(brownfield(ok)), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["semantic_elevation"] == {"static": "SSM-001", "dynamic": "DSM-001"}

    empty = tmp_path / "empty"
    empty.mkdir()
    assert main([*args, str(empty)]) == 2
    assert "elevation.static_missing" in capsys.readouterr().err

    trivial = str(ROOT / "tests" / "fixtures" / "pathways" / "trivial-change.md")
    assert (
        main(
            ["plan-validate", trivial, "--pathway", "trivial-change", "--depth", "standard", "--artifacts", str(empty)]
        )
        == 0
    )


def test_build_graph_accepts_parsed_documents_directly():
    text = doc("intent", "INT-001")
    graph = build_graph([("mem.md", text, parse_artifact(text))])
    assert list(graph.nodes) == ["INT-001"] and graph.dangling == ()
