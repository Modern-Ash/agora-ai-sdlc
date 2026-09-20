"""Independent-review policy profiles for producer/reviewer separation.

This module is deliberately local and deterministic. Agora Core remains the
lifecycle authority; these functions evaluate review records before a caller
records an approval or evidence in Core.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from agora_ai_sdlc.artifacts import Artifact
from agora_ai_sdlc.provenance import Provenance, evaluate_separation, normalize

SCHEMA = "agora-ai-sdlc/independent-review/v1"
CRITICAL_ARTIFACT_KINDS = {
    "requirements",
    "architecture",
    "threat-model",
    "test-strategy",
    "implementation-plan",
    "deployment-plan",
    "rollback-procedure",
    "operational-readiness",
}
APPROVED_VERDICTS = {"approved", "approved-with-observations"}
HUMAN_KINDS = {"human"}
AUTHORIZED_WAIVER_ROLES = {"governance-owner"}


class ReviewPolicyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class Profile:
    name: str
    dimensions: tuple[str, ...] = ()
    requires_human_final: bool = False
    waiver_allowed: bool = True
    human_final_waivable: bool = True
    min_source: str = "declared"


@dataclass(frozen=True)
class ResolvedProfile:
    names: tuple[str, ...]
    dimensions: tuple[str, ...]
    requires_human_final: bool
    waiver_allowed: bool
    human_final_waivable: bool
    min_source: str


@dataclass(frozen=True)
class ArtifactRevision:
    kind: str
    id: str
    revision: int
    digest: str
    policy: tuple[str, ...]


@dataclass(frozen=True)
class Review:
    actor: str
    actor_kind: str
    role: str
    subject: ArtifactRevision
    verdict: str
    provenance: Provenance


@dataclass(frozen=True)
class Waiver:
    actor: str
    role: str
    reason: str
    evidence: str


PROFILES = {
    "distinct-actor": Profile("distinct-actor", dimensions=("actor",)),
    "distinct-runtime": Profile("distinct-runtime", dimensions=("runtime",)),
    "distinct-provider": Profile("distinct-provider", dimensions=("provider",)),
    "human-final": Profile("human-final", requires_human_final=True),
    "regulated": Profile(
        "regulated",
        dimensions=("actor", "provider"),
        requires_human_final=True,
        human_final_waivable=False,
        min_source="observed",
    ),
}


def resolve_profiles(names: Iterable[str]) -> ResolvedProfile:
    requested = set(names)
    selected = tuple(name for name in PROFILES if name in requested)
    if not selected:
        raise ReviewPolicyError("review.profile", "at least one independent-review profile is required")
    unknown = sorted(requested - set(PROFILES))
    if unknown:
        raise ReviewPolicyError("review.profile", f"unknown independent-review profile(s): {', '.join(unknown)}")
    profiles = [PROFILES[name] for name in selected]
    dimensions = tuple(
        dim for dim in ("actor", "runtime", "provider", "model") if any(dim in p.dimensions for p in profiles)
    )
    return ResolvedProfile(
        names=selected,
        dimensions=dimensions,
        requires_human_final=any(p.requires_human_final for p in profiles),
        waiver_allowed=all(p.waiver_allowed for p in profiles),
        human_final_waivable=all(p.human_final_waivable for p in profiles),
        min_source="observed" if any(p.min_source == "observed" for p in profiles) else "declared",
    )


def artifact_revision(artifact: Artifact, digest: str) -> ArtifactRevision:
    policy = artifact.front.get("separation-policy")
    if not isinstance(policy, list) or not policy or not all(isinstance(item, str) for item in policy):
        raise ReviewPolicyError("review.policy", f"{artifact.id} must declare separation-policy")
    revision = artifact.front.get("revision")
    if not isinstance(revision, int) or revision < 1:
        raise ReviewPolicyError("review.revision", f"{artifact.id} must declare a positive integer revision")
    if not isinstance(digest, str) or not digest.strip():
        raise ReviewPolicyError("review.digest", f"{artifact.id} needs a non-empty artifact digest")
    resolve_profiles(policy)
    return ArtifactRevision(artifact.kind, artifact.id, revision, digest.strip(), tuple(policy))


def check_critical_artifact_policy(artifact: Artifact) -> None:
    if artifact.kind in CRITICAL_ARTIFACT_KINDS:
        artifact_revision(artifact, "template-or-content-digest")


def _waiver_blockers(profile: ResolvedProfile, waiver: Waiver | None) -> list[dict[str, str]]:
    if waiver is None:
        return []
    blockers = []
    if not profile.waiver_allowed:
        blockers.append({"code": "review.waiver.profile", "message": "active profile does not allow waivers"})
    if waiver.role not in AUTHORIZED_WAIVER_ROLES:
        blockers.append(
            {"code": "review.waiver.role", "message": f"{waiver.role} is not authorized to waive review policy"}
        )
    for field in ("actor", "reason", "evidence"):
        if not str(getattr(waiver, field) or "").strip():
            blockers.append({"code": f"review.waiver.{field}", "message": f"waiver.{field} is required"})
    return blockers


def evaluate_review(
    *,
    produced: ArtifactRevision,
    producer: Provenance,
    review: Review,
    profiles: Iterable[str] | None = None,
    waiver: Waiver | None = None,
) -> dict:
    """Return a deterministic decision for a review of an exact artifact revision."""
    profile = resolve_profiles(profiles or produced.policy)
    blockers: list[dict[str, str]] = []
    waived: list[dict[str, str]] = []
    expected_subject = {
        "kind": produced.kind,
        "id": produced.id,
        "revision": produced.revision,
        "digest": produced.digest,
    }
    if producer.subject != expected_subject:
        blockers.append(
            {
                "code": "review.production_subject",
                "message": "producer provenance is not bound to the exact artifact id, revision and digest",
            }
        )
    if normalize(review.actor) != normalize(review.provenance.actor):
        blockers.append(
            {
                "code": "review.provenance.actor",
                "message": "review actor does not match reviewer provenance actor",
            }
        )
    if review.subject != produced:
        blockers.append(
            {
                "code": "review.stale",
                "message": "review subject does not match the produced artifact id, revision and digest",
            }
        )
    if review.verdict not in APPROVED_VERDICTS:
        blockers.append({"code": "review.verdict", "message": f"review verdict {review.verdict!r} is not approving"})

    separation = evaluate_separation(list(profile.dimensions), producer, review.provenance, profile.min_source)
    policy_blockers = [{"code": f"review.separation.{b['dimension']}", **b} for b in separation["blockers"]]
    if profile.requires_human_final and review.actor_kind not in HUMAN_KINDS:
        policy_blockers.append(
            {
                "code": "review.human_final",
                "dimension": "human-final",
                "status": "same",
                "message": "final review requires a human reviewer",
            }
        )

    waiver_errors = _waiver_blockers(profile, waiver)
    if waiver_errors:
        blockers.extend(waiver_errors)
        blockers.extend(policy_blockers)
    elif waiver is None:
        blockers.extend(policy_blockers)
    else:
        for blocker in policy_blockers:
            if blocker["code"] == "review.human_final" and not profile.human_final_waivable:
                blockers.append(
                    {
                        "code": "review.waiver.human_final",
                        "message": "regulated profile cannot waive required human final approval",
                    }
                )
            else:
                waived.append(blocker)

    return {
        "allowed": not blockers,
        "profile": profile.names,
        "blockers": blockers,
        "waived": waived,
    }
