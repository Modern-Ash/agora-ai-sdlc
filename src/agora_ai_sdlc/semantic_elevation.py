"""Brown-field semantic elevation: static and dynamic system models required before Construction."""

from __future__ import annotations

from agora_ai_sdlc.adaptive_planning import PathwayPolicy
from agora_ai_sdlc.artifacts import Artifact

STATIC_STEP = "brownfield-static-model"
DYNAMIC_STEP = "brownfield-dynamic-model"


class SemanticElevationError(ValueError):
    """Stable failure for missing or unlinked system models."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def requires_elevation(pathway: PathwayPolicy) -> bool:
    """Data-driven: a pathway requires elevation when its policy makes both model steps mandatory."""

    return STATIC_STEP in pathway.mandatory_steps and DYNAMIC_STEP in pathway.mandatory_steps


def _ancestor_kinds(start: Artifact, by_id: dict[str, Artifact]) -> set[str]:
    kinds: set[str] = set()
    seen = {start.id}
    stack = list(start.traces_to)
    while stack:
        current = stack.pop()
        if current in seen or current not in by_id:
            continue
        seen.add(current)
        kinds.add(by_id[current].kind)
        stack.extend(by_id[current].traces_to)
    return kinds


def validate_semantic_elevation(artifacts: list[Artifact], work: str) -> tuple[str, str]:
    """Return (static, dynamic) model ids for `work`, or fail closed."""

    by_id = {artifact.id: artifact for artifact in artifacts}
    scoped = [a for a in artifacts if a.front.get("work") == work]
    static = sorted(a.id for a in scoped if a.kind == "static-system-model")
    dynamic = sorted(a.id for a in scoped if a.kind == "dynamic-system-model")
    if not static:
        raise SemanticElevationError("elevation.static_missing", f"no static-system-model for work {work!r}")
    if not dynamic:
        raise SemanticElevationError("elevation.dynamic_missing", f"no dynamic-system-model for work {work!r}")
    if not any("legacy-inventory" in _ancestor_kinds(by_id[s], by_id) for s in static):
        raise SemanticElevationError(
            "elevation.static_unsourced", "static-system-model must trace to a legacy-inventory"
        )
    linked = [
        d for d in dynamic if any(by_id[t].kind == "static-system-model" for t in by_id[d].traces_to if t in by_id)
    ]
    if not linked:
        raise SemanticElevationError(
            "elevation.dynamic_unlinked", "dynamic-system-model must trace to a static-system-model"
        )
    return static[0], linked[0]
