"""Shared fake runtimes and provider-neutral scenario builders for conformance and parity tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

from agora_ai_sdlc.claude_code_adapter import ClaudeCodeAdapter
from agora_ai_sdlc.codex_adapter import CodexAdapter
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_candidate import Candidate
from agora_ai_sdlc.execution_envelope import CoreSnapshot, build_envelope
from agora_ai_sdlc.execution_requirements import requirements_for
from agora_ai_sdlc.opencode_adapter import OpenCodeAdapter
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding

ACTOR = "project:developer"
COMMIT = "a" * 40


def bundle(stage="construction", next_action="inspect-next"):
    return ExecutionBundle(
        schema="s", swarm="delivery", work="issue-26", stage=stage, next_action=next_action, branch=None,
        base_branch=None, head=None, objective="o", acceptance_criteria=(), changed_paths=(), dirty_paths=(),
        related_paths=(), languages=(), build_systems=(), verification_commands=(), risks=(),
        governance={}, deterministic_inception_path=None,
    )  # fmt: skip


def snapshot(*, human=False, revision="rev-4"):
    return CoreSnapshot("delivery", "issue-26", revision, "construction", "operations", "builder",
                        {"builder": ACTOR}, frozenset({ACTOR}), human)  # fmt: skip


def candidate():
    return Candidate("Modern-Ash/x", "delivery", "issue-26", "rev-4", "commit", COMMIT, None, ("a.txt",), ())


BINDINGS = {
    "claude": RuntimeBinding(AgentRuntimeRef("claude", "claude-code"), ModelRuntimeRef("anthropic", "anthropic", "claude-sonnet-x")),
    "codex": RuntimeBinding(AgentRuntimeRef("codex", "codex"), ModelRuntimeRef("openai", "openai", "gpt-5-codex")),
    "opencode-cloud": RuntimeBinding(AgentRuntimeRef("opencode", "opencode"), ModelRuntimeRef("acme", "acme", "big-1")),
    "opencode-ollama": RuntimeBinding(AgentRuntimeRef("opencode", "opencode"), ModelRuntimeRef("ollama", "ollama", "qwen2.5-coder:7b")),
}  # fmt: skip


def adapters(root: Path):
    ok = lambda command: (0, "9.9.9")
    return {
        "claude": ClaudeCodeAdapter(executable="/bin/claude", probe=lambda c: (0, "2.1.281")),
        "codex": CodexAdapter(executable="/bin/codex", probe=lambda c: (0, "codex-cli 0.156.1")),
        "opencode-cloud": OpenCodeAdapter(root=root, executable="/bin/opencode", probe=ok),
        "opencode-ollama": OpenCodeAdapter(root=root, executable="/bin/opencode", probe=ok),
    }  # fmt: skip


def envelope(binding, *, human=False, revision="rev-4", with_candidate=True, req=None):
    return build_envelope(
        snapshot(human=human, revision=revision), req or requirements_for(bundle()), binding, bundle(),
        actor_id=ACTOR, candidate=candidate().envelope_reference() if with_candidate else None,
    ).to_dict()  # fmt: skip


def observed(*, ollama_models=("qwen2.5-coder:7b",)):
    def one(name, **extra):
        return RuntimeDiscovery(name, name, name, True, f"/bin/{name}", True, "1", True, **extra)

    return {
        "claude": one("claude"), "codex": one("codex"), "opencode": one("opencode"),
        "ollama": one("ollama", service="responsive", models=tuple(ollama_models)),
        "anthropic": one("anthropic"), "openai": one("openai"), "acme": one("acme"),
    }  # fmt: skip


def fake_result(exit_code=0, output="done"):
    return subprocess.CompletedProcess([], exit_code, stdout=output, stderr="")
