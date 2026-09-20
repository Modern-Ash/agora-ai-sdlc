"""Depth profiles: deterministic resolution of AI-SDLC gate obligations.

Profiles are declarative data. The `standard` depth equals the Method Pack gates, which is what Agora Core
enforces. Other depths are resolved on top of it; obligations beyond the pack gates are reported by
`assess`, they are not enforced by Core gates.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

SCHEMA = "agora-ai-sdlc/depth-profile/v1"
ORDER = ("minimal", "standard", "comprehensive", "regulated")
DEFAULT = "standard"
FIELDS = ("artifacts", "evidence", "approvals")
# Obligations no depth may remove.
PROTECTED = {("intent-framed", "approvals", "product-owner")}


class ProfileError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def asset_root(name: str) -> Path:
    packaged = Path(__file__).parent / name
    return packaged if packaged.is_dir() else Path(__file__).parent.parent.parent / name


def _list(front: dict, key: str) -> list[str]:
    value = front.get(key, "[]").strip()
    return json.loads(value) if value.startswith("[") else []


def baseline() -> dict[str, dict[str, tuple[str, ...]]]:
    """Gate obligations read from the Method Pack (single source of truth)."""
    gates: dict[str, dict[str, tuple[str, ...]]] = {}
    for path in sorted((asset_root("registry") / "methods" / "ai-sdlc" / "gates").glob("*.md")):
        front = {}
        lines = path.read_text().split("\n")
        for line in lines[1 : lines.index("---", 1)]:
            key, _, value = line.partition(":")
            front[key.strip()] = value.strip()
        gate_id = json.loads(front["id"])
        gates[gate_id] = {
            "artifacts": tuple(_list(front, "required-artifacts")),
            "evidence": tuple(_list(front, "required-evidence-types")),
            "approvals": tuple(_list(front, "required-approval-roles")),
        }
    return gates


def _load(depth: str) -> dict:
    path = asset_root("profiles") / "depth" / f"{depth}.yaml"
    if depth not in ORDER or not path.is_file():
        raise ProfileError("profile.unknown", f"unknown depth profile {depth!r}; expected one of {', '.join(ORDER)}")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("id") != depth:
        raise ProfileError("profile.invalid", f"{path.name} is not a valid {SCHEMA} profile for {depth!r}")
    return data


@dataclass(frozen=True)
class ResolvedProfile:
    id: str
    gates: dict[str, dict[str, tuple[str, ...]]]
    requires: dict[str, bool]

    def snapshot(self) -> dict:
        return {"id": self.id, "gates": {g: {k: list(v) for k, v in f.items()} for g, f in sorted(self.gates.items())},
                "requires": dict(sorted(self.requires.items()))}  # fmt: skip


def _apply(gates: dict, delta: dict, sign: int) -> None:
    for gate, fields in (delta.get("gates") or {}).items():
        if gate not in gates:
            raise ProfileError("profile.unknown_gate", f"profile references unknown gate {gate!r}")
        for field, items in fields.items():
            if field not in FIELDS:
                raise ProfileError("profile.invalid", f"unknown obligation field {field!r}")
            current = list(gates[gate][field])
            for item in items:
                if sign > 0 and item not in current:
                    current.append(item)
                if sign < 0:
                    if (gate, field, item) in PROTECTED:
                        raise ProfileError("profile.protected", f"{item} approval at {gate} cannot be removed")
                    if item not in current:
                        raise ProfileError("profile.invalid", f"cannot remove {item!r} from {gate}.{field}")
                    current.remove(item)
            gates[gate][field] = tuple(current)


def resolve(depth: str | None = None) -> ResolvedProfile:
    depth = DEFAULT if depth is None else depth
    chain = []
    current: str | None = depth
    while current is not None:
        data = _load(current)
        chain.append(data)
        current = data.get("extends")
        if len(chain) > len(ORDER):
            raise ProfileError("profile.cycle", "profile inheritance cycle")
    gates = {g: dict(f) for g, f in baseline().items()}
    requires: dict[str, bool] = {}
    for data in reversed(chain):
        _apply(gates, data.get("add") or {}, +1)
        removal = data.get("remove") or {}
        if removal and not str(removal.get("justification", "")).strip():
            raise ProfileError("profile.unjustified", f"{data['id']} removes obligations without justification")
        _apply(gates, removal, -1)
        requires.update(data.get("requires") or {})
    return ResolvedProfile(depth, gates, requires)


def is_monotonic(lower: ResolvedProfile, higher: ResolvedProfile) -> bool:
    return all(set(lower.gates[g][f]) <= set(higher.gates[g][f]) for g in lower.gates for f in FIELDS) and all(
        higher.requires.get(k, False) or not v for k, v in lower.requires.items()
    )


def assess(depth: str, gate: str, artifacts: set[str], evidence: set[str], approvals: set[str]) -> dict:
    """Read-only: list obligations of `gate` at `depth` not yet met. Never mutates work."""
    profile = resolve(depth)
    if gate not in profile.gates:
        raise ProfileError("profile.unknown_gate", f"unknown gate {gate!r}")
    have = {"artifacts": artifacts, "evidence": evidence, "approvals": approvals}
    missing = {f: [i for i in profile.gates[gate][f] if i not in have[f]] for f in FIELDS}
    return {"depth": depth, "gate": gate, "missing": {k: v for k, v in missing.items() if v},
            "requires": profile.requires}  # fmt: skip


LEVELS = {"low": 0, "medium": 1, "high": 2}


def recommend(risk: str, reversibility: str, data_sensitivity: str, operational_impact: str) -> str:
    """Deterministic depth recommendation. reversibility: reversible|hard|irreversible;
    data_sensitivity: public|internal|confidential|regulated; risk/impact: low|medium|high."""
    if data_sensitivity == "regulated":
        return "regulated"
    if risk not in LEVELS or operational_impact not in LEVELS:
        raise ProfileError("profile.criteria", "risk and operational_impact must be low, medium or high")
    if reversibility not in ("reversible", "hard", "irreversible") or data_sensitivity not in (
        "public", "internal", "confidential",
    ):  # fmt: skip
        raise ProfileError("profile.criteria", "invalid reversibility or data_sensitivity")
    score = max(LEVELS[risk], LEVELS[operational_impact], {"reversible": 0, "hard": 1, "irreversible": 2}[reversibility],
                {"public": 0, "internal": 0, "confidential": 2}[data_sensitivity])  # fmt: skip
    return ("minimal", "standard", "comprehensive")[score]
