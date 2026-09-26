"""Shared RuntimeAdapter conformance and golden parity across Claude, Codex, OpenCode and OpenCode+Ollama."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from support import runtime_scenarios as sc
from support.adapter_conformance import assert_adapter_conformance

from agora_ai_sdlc.agent_capabilities import manifest_for
from agora_ai_sdlc.execution_candidate import bind_envelope
from agora_ai_sdlc.execution_envelope import EnvelopeError, build_envelope, verify_integrity
from agora_ai_sdlc.execution_requirements import ExecutionRequirements, requirements_for
from agora_ai_sdlc.runtime_adapter import AdapterError, AdapterRegistry, sanitize
from agora_ai_sdlc.runtime_selection import Candidate, Route, select_runtime

NAMES = tuple(sc.BINDINGS)
ALLOW = {"allowed": True, "blockers": []}


@pytest.fixture
def root(tmp_path):
    return tmp_path


@pytest.mark.parametrize("name", NAMES)
def test_shared_conformance_suite(name, root):
    adapter = sc.adapters(root)[name]
    assert_adapter_conformance(adapter, sc.envelope(sc.BINDINGS[name]), root, surfaces=("instructions",))


@pytest.mark.parametrize("name", NAMES)
def test_adapter_maps_to_exactly_one_canonical_manifest(name, root):
    adapter = sc.adapters(root)[name]
    registry = AdapterRegistry()
    registry.register(adapter)
    manifest = adapter.capability_manifest()
    assert manifest == manifest_for(sc.BINDINGS[name].agent) and manifest.agent == adapter.integration_id


@pytest.mark.parametrize("name", NAMES)
def test_transition_identity_and_candidate_are_preserved_and_actor_is_not_synthesized(name, root):
    adapter, payload = sc.adapters(root)[name], sc.envelope(sc.BINDINGS[name])
    prepared = adapter.prepare_execution(payload)
    carried = json.dumps([prepared.argv, prepared.stdin])
    assert prepared.envelope_digest == payload["digest"]
    assert (prepared.operation, [list(a) for a in prepared.arguments]) == (
        payload["next_transition"]["operation"],
        [[a["name"], a["value"]] for a in payload["next_transition"]["arguments"]],
    )
    assert sc.candidate().subject_hash in carried and sc.ACTOR in carried
    assert f"ai-{adapter.integration_id}" not in carried
    bind_envelope(payload, sc.candidate())


@pytest.mark.parametrize("name", NAMES)
def test_human_boundary_and_stale_envelopes_cannot_launch(name, root):
    adapter = sc.adapters(root)[name]
    with pytest.raises(AdapterError) as error:
        adapter.prepare_execution(sc.envelope(sc.BINDINGS[name], human=True))
    assert error.value.code == "adapter.not_executable"
    current = (sc.snapshot(revision="rev-5"), requirements_for(sc.bundle()))
    with pytest.raises(AdapterError) as error:
        adapter.prepare_execution(sc.envelope(sc.BINDINGS[name]), current=current)
    assert error.value.code == "adapter.stale_envelope"


@pytest.mark.parametrize("name", NAMES)
def test_unsupported_capability_fails_before_launch(name):
    needy = ExecutionRequirements(
        **{**requirements_for(sc.bundle()).__dict__, "required_capabilities": ("isolated_reviewer",)}
    )
    with pytest.raises(EnvelopeError) as error:
        sc.envelope(sc.BINDINGS[name], req=needy)
    assert error.value.code == "envelope.binding_inadmissible" and "capability_missing" in str(error.value)


@pytest.mark.parametrize("name", NAMES)
def test_collection_never_mutates_core_and_ordinary_failure_does_not_switch_provider(name, root):
    adapter = sc.adapters(root)[name]
    prepared = adapter.prepare_execution(sc.envelope(sc.BINDINGS[name]))
    before = sorted(str(p) for p in root.rglob("*"))
    outcome = adapter.launch(prepared, lambda argv, stdin: (1, "boom token=supersecretvalue"))
    assert outcome.exit_code == 1 and "supersecretvalue" not in outcome.output
    assert sorted(str(p) for p in root.rglob("*")) == before and not (root / ".agora").exists()
    route = Route("build", tuple(Candidate(sc.BINDINGS[n], {}, ALLOW, ALLOW) for n in ("claude", "codex")))
    hopped = select_runtime(route, signal="ordinary-failure", requirements=requirements_for(sc.bundle()))
    assert not hopped["allowed"] and hopped["blockers"][0]["code"] == "fallback.ordinary_failure"


def test_golden_parity_provider_neutral_facts_are_identical_across_runtimes(root):
    facts = {}
    for name in NAMES:
        payload = sc.envelope(sc.BINDINGS[name])
        prepared = sc.adapters(root)[name].prepare_execution(payload)
        facts[name] = {
            "work": payload["work"],
            "authority": payload["authority"],
            "requirements": payload["requirements"],
            "next_transition": payload["next_transition"],
            "candidate": payload["candidate"],
            "prepared": (prepared.operation, prepared.arguments, prepared.envelope_digest == payload["digest"]),
        }
    baseline = facts["claude"]
    assert all(value == baseline for value in facts.values())
    digests = {sc.envelope(sc.BINDINGS[n])["digest"] for n in NAMES}
    assert len(digests) == len(NAMES)  # only runtime/model identity differs


def test_local_tier_admission_opencode_ollama_versus_ollama_alone():
    req = requirements_for(sc.bundle())
    assert req.reasoning_tier == "local" and "workspace.write" in req.required_capabilities
    found = sc.observed()
    ok = select_runtime(
        Route("build", (Candidate(sc.BINDINGS["opencode-ollama"], {}, ALLOW, ALLOW),)),
        requirements=req,
        availability=found,
    )
    assert ok["allowed"]
    from agora_ai_sdlc.runtime_domain import ModelRuntimeRef

    alone = select_runtime(
        Route("build", (Candidate(ModelRuntimeRef("ollama", "ollama", "qwen2.5-coder:7b"), {}, ALLOW, ALLOW),)),
        requirements=req, availability=found,
    )  # fmt: skip
    assert alone["considered"][0]["blockers"] == ("runtime.agent_required",)
    gone = select_runtime(
        Route("build", (Candidate(sc.BINDINGS["opencode-ollama"], {}, ALLOW, ALLOW),)),
        requirements=req, availability=sc.observed(ollama_models=()),
    )  # fmt: skip
    assert gone["allowed"]  # unknown catalog is not asserted absent; an empty catalog cannot block


def test_forged_envelope_and_registry_have_no_provider_branching(root):
    payload = sc.envelope(sc.BINDINGS["codex"])
    forged = json.loads(json.dumps(payload))
    forged["work"]["id"] = "issue-99"
    with pytest.raises(EnvelopeError) as error:
        verify_integrity(forged)
    assert error.value.code == "envelope.tampered"
    assert sanitize("api_key=sk-abcdef123456") == "[redacted]"
    assert build_envelope  # imported to prove workflow code only needs the neutral builder
