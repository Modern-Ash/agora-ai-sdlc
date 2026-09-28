"""Deterministic bounded-context manifest around Laya-pruned repository context."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from agora_ai_sdlc.context_graph import estimate_tokens
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_context import ExecutionContextSelection

SCHEMA = "agora-ai-sdlc/context-manifest/v1"
_SENSITIVE_NAMES = {".env", ".env.local", ".env.production", "credentials.json", "secrets.json"}


def _sensitive_path(path: str) -> bool:
    candidate = Path(path)
    lowered = path.casefold()
    return candidate.name.casefold() in _SENSITIVE_NAMES or any(
        marker in lowered for marker in ("/secrets/", "/credentials/", ".pem", ".key")
    )


class ContextOverflowError(ValueError):
    """Mandatory governed context alone exceeds the selected runtime limit."""

    def __init__(self, required_tokens: int, limit_tokens: int):
        super().__init__(
            f"context.mandatory_overflow: required~{required_tokens} estimated tokens "
            f"exceed runtime limit {limit_tokens}"
        )
        self.required_tokens = required_tokens
        self.limit_tokens = limit_tokens


@dataclass(frozen=True)
class ContextItem:
    id: str
    kind: str
    mandatory: bool
    provenance: str
    estimated_tokens: int
    digest: str


@dataclass(frozen=True)
class ContextManifest:
    schema: str
    work: str | None
    head: str | None
    mandatory: tuple[ContextItem, ...]
    selected_optional: tuple[ContextItem, ...]
    available_optional: tuple[ContextItem, ...]
    estimated_tokens: int
    runtime_limit_tokens: int | None
    overflow: bool = False

    def snapshot(self) -> dict:
        return asdict(self)


def _item(identifier: str, kind: str, mandatory: bool, provenance: str, text: str) -> ContextItem:
    return ContextItem(
        id=identifier,
        kind=kind,
        mandatory=mandatory,
        provenance=provenance,
        estimated_tokens=estimate_tokens(text),
        digest="sha256:" + hashlib.sha256(text.encode()).hexdigest(),
    )


def _mandatory(bundle: ExecutionBundle) -> tuple[ContextItem, ...]:
    values = [
        (
            "work-identity",
            "governance",
            "execution-bundle",
            json.dumps(
                {
                    "swarm": bundle.swarm,
                    "work": bundle.work,
                    "head": bundle.head,
                    "stage": bundle.stage,
                    "next_action": bundle.next_action,
                    "branch": bundle.branch,
                    "base_branch": bundle.base_branch,
                },
                sort_keys=True,
            ),
        ),
        (
            "acceptance-criteria",
            "requirements",
            "execution-bundle.acceptance_criteria",
            json.dumps(list(bundle.acceptance_criteria), sort_keys=True),
        ),
        (
            "governance",
            "governance",
            "execution-bundle.governance",
            json.dumps(bundle.governance, sort_keys=True),
        ),
        (
            "risk-policy",
            "policy",
            "execution-bundle.risks",
            json.dumps(list(bundle.risks), sort_keys=True),
        ),
        (
            "verification",
            "verification",
            "execution-bundle.verification_commands",
            json.dumps(list(bundle.verification_commands), sort_keys=True),
        ),
    ]
    return tuple(_item(identifier, kind, True, provenance, text) for identifier, kind, provenance, text in values)


def _path_item(root: Path, path: str, *, selected: bool) -> ContextItem:
    candidate = root / path
    if _sensitive_path(path):
        content = "[sensitive content omitted]"
    else:
        try:
            content = candidate.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeError):
            content = ""
    return _item(
        path,
        "repository-file",
        False,
        f"repository:{path}",
        content if selected else path,
    )


def build_context_manifest(
    root: Path,
    bundle: ExecutionBundle,
    selection: ExecutionContextSelection,
    *,
    runtime_limit_tokens: int | None = None,
) -> ContextManifest:
    """Build a reproducible manifest; Laya-selected context cannot remove mandatory items."""

    mandatory = _mandatory(bundle)
    required = sum(item.estimated_tokens for item in mandatory)
    if runtime_limit_tokens is not None and required > runtime_limit_tokens:
        raise ContextOverflowError(required, runtime_limit_tokens)

    selected = tuple(_path_item(root, path, selected=True) for path in selection.selected_paths)
    available = tuple(
        _path_item(root, path, selected=False)
        for path in selection.candidate_paths
        if path not in selection.selected_paths
    )
    total = required + sum(item.estimated_tokens for item in selected)
    overflow = runtime_limit_tokens is not None and total > runtime_limit_tokens
    return ContextManifest(
        schema=SCHEMA,
        work=bundle.work,
        head=bundle.head,
        mandatory=mandatory,
        selected_optional=selected,
        available_optional=available,
        estimated_tokens=total,
        runtime_limit_tokens=runtime_limit_tokens,
        overflow=overflow,
    )


def persist_context_manifest(root: Path, work: str, manifest: ContextManifest) -> Path:
    target = root / ".agora" / "ai-sdlc" / "bundles" / work / "CONTEXT_MANIFEST.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest.snapshot(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
