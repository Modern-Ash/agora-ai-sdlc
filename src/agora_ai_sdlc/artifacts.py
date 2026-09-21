"""Schema-versioned AI-SDLC artifact documents: parsing, validation and traceability checks.

Pure functions over text; no network, no provider assumptions.
"""

import re
from dataclasses import dataclass

import yaml

SCHEMA = "agora-ai-sdlc/artifact/v1"
ID_PATTERN = re.compile(r"^[A-Z]{3}-\d{3}$")
SLUG = re.compile(r"^[a-z][a-z0-9-]*$")
PREFIX = {
    "readiness-assessment": "RDY", "intent": "INT", "clarification": "CLR", "unit-of-work": "UOW",
    "requirements": "REQ", "domain-model": "DOM", "architecture": "ARC", "threat-model": "THR",
    "test-strategy": "TST", "implementation-plan": "IMP", "deployment-plan": "DEP",
    "rollback-procedure": "RBK", "operational-readiness": "OPR", "learning-record": "LRN",
    "rework-record": "RWK",
    "legacy-inventory": "LGI", "dependency-map": "DPM", "characterization": "CHR",
    "target-architecture": "TAR", "migration-plan": "MGP", "migration-slice": "MGS",
    "conversion-record": "CNV", "equivalence-report": "EQV", "cutover-plan": "CUT",
    "stabilization-report": "STB",
    "user-stories": "USR", "prfaq": "PRF", "risk-register": "RSK", "measurement-criteria": "MSR",
    "bolt-plan": "BLT", "logical-design": "LGD", "deployment-units": "DPU", "plan": "PLN",
}  # fmt: skip
# kind -> kinds it may trace to. Empty tuple = root (needs no parent); None = may trace to any kind.
PARENTS: dict[str, tuple[str, ...] | None] = {
    "readiness-assessment": (), "intent": (), "clarification": None,
    "unit-of-work": ("intent",), "requirements": ("unit-of-work",),
    "domain-model": ("requirements",), "architecture": ("requirements",),
    "threat-model": ("architecture",), "test-strategy": ("requirements",),
    "implementation-plan": ("architecture", "test-strategy"),
    "deployment-plan": ("implementation-plan",), "rollback-procedure": ("deployment-plan",),
    "operational-readiness": ("deployment-plan",), "learning-record": None, "rework-record": None,
    "legacy-inventory": (), "dependency-map": ("legacy-inventory",),
    "characterization": ("legacy-inventory",),
    "target-architecture": ("dependency-map", "characterization"),
    "migration-plan": ("target-architecture", "characterization"),
    "migration-slice": ("migration-plan",), "conversion-record": ("migration-slice",),
    "equivalence-report": ("characterization", "conversion-record", "migration-slice"),
    "cutover-plan": ("migration-plan", "equivalence-report"),
    "stabilization-report": ("cutover-plan",),
    "user-stories": ("unit-of-work",), "prfaq": ("intent",), "risk-register": ("intent",),
    "measurement-criteria": ("intent",), "bolt-plan": ("unit-of-work", "user-stories"),
    "logical-design": ("domain-model", "requirements"), "deployment-units": ("implementation-plan",),
    "plan": None,
}  # fmt: skip
# Template file (without .md) per kind when it differs from the kind name.
TEMPLATE_FILES = {"intent": "product-intent"}


class ArtifactError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class Artifact:
    kind: str
    id: str
    traces_to: tuple[str, ...]
    criteria: tuple[str, ...]
    covers_criteria: tuple[str, ...]
    sections: tuple[str, ...]
    front: dict


def split(text: str) -> tuple[dict, str]:
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0] != "---":
        raise ArtifactError("artifact.front_matter", "document must start with front matter")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise ArtifactError("artifact.front_matter", "unterminated front matter") from error
    try:
        front = yaml.safe_load("\n".join(lines[1:end])) or {}
    except yaml.YAMLError as error:
        raise ArtifactError("artifact.front_matter", "front matter is not valid YAML") from error
    if not isinstance(front, dict):
        raise ArtifactError("artifact.front_matter", "front matter must be a mapping")
    return front, "\n".join(lines[end + 1 :])


def sections_of(body: str) -> tuple[str, ...]:
    return tuple(m.group(1).strip() for m in re.finditer(r"^## (.+)$", body, re.MULTILINE))


def _strings(front: dict, key: str) -> tuple[str, ...]:
    value = front.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ArtifactError("artifact.type", f"{key!r} must be a list of strings")
    return tuple(value)


def _common(front: dict, body: str) -> Artifact:
    if front.get("schema") != SCHEMA:
        raise ArtifactError("artifact.schema", f"unsupported schema {front.get('schema')!r}; expected {SCHEMA}")
    kind = front.get("kind")
    if kind not in PREFIX:
        raise ArtifactError("artifact.kind", f"unknown kind {kind!r}")
    if front.get("version") != 1:
        raise ArtifactError("artifact.version", f"unsupported version {front.get('version')!r}")
    required = _strings(front, "required-sections")
    if not required:
        raise ArtifactError("artifact.type", "'required-sections' must not be empty")
    present = sections_of(body)
    missing = [s for s in required if s not in present]
    if missing:
        raise ArtifactError("artifact.missing_section", f"missing required sections: {', '.join(missing)}")
    return Artifact(
        kind=kind, id=str(front.get("id") or ""), traces_to=_strings(front, "traces-to"),
        criteria=_strings(front, "criteria"), covers_criteria=_strings(front, "covers-criteria"),
        sections=present, front=front,
    )  # fmt: skip


def parse_template(text: str) -> Artifact:
    front, body = split(text)
    return _common(front, body)


def parse_artifact(text: str) -> Artifact:
    """Validate a filled artifact: template rules plus a well-formed, kind-matching id."""
    artifact = parse_template(text)
    if not ID_PATTERN.match(artifact.id) or not artifact.id.startswith(PREFIX[artifact.kind] + "-"):
        raise ArtifactError("artifact.id", f"id {artifact.id!r} must match {PREFIX[artifact.kind]}-NNN")
    for ref in artifact.traces_to:
        if not ID_PATTERN.match(ref):
            raise ArtifactError("artifact.trace_format", f"malformed trace id {ref!r}")
    for criterion in artifact.criteria + artifact.covers_criteria:
        if not SLUG.match(criterion):
            raise ArtifactError("artifact.criterion", f"malformed criterion id {criterion!r}")
    return artifact


def check_traceability(artifacts: list[Artifact]) -> None:
    """Deterministic cross-artifact checks: unique ids, resolvable references, allowed parent kinds,
    and every requirement criterion covered by a test strategy."""
    by_id: dict[str, Artifact] = {}
    for a in artifacts:
        if a.id in by_id:
            raise ArtifactError("trace.duplicate_id", f"duplicate id {a.id}")
        by_id[a.id] = a
    for a in artifacts:
        allowed = PARENTS[a.kind]
        if allowed is not None and allowed and not a.traces_to:
            raise ArtifactError("trace.missing_parent", f"{a.id} ({a.kind}) must trace to {'/'.join(allowed)}")
        for ref in a.traces_to:
            if ref not in by_id:
                raise ArtifactError("trace.dangling", f"{a.id} traces to unknown {ref}")
            if allowed is not None and by_id[ref].kind not in allowed:
                raise ArtifactError("trace.parent_kind", f"{a.id} ({a.kind}) cannot trace to {ref} ({by_id[ref].kind})")
    declared = {c for a in artifacts if a.kind == "requirements" for c in a.criteria}
    covered = {c for a in artifacts if a.kind == "test-strategy" for c in a.covers_criteria}
    unknown = sorted(covered - declared)
    if unknown:
        raise ArtifactError(
            "trace.unknown_criterion", f"test strategy covers undeclared criteria: {', '.join(unknown)}"
        )
    uncovered = sorted(declared - covered)
    if uncovered:
        raise ArtifactError("trace.uncovered_criterion", f"criteria without test coverage: {', '.join(uncovered)}")
