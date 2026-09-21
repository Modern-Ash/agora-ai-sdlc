"""Vendor-neutral enterprise review-gate policy bundles.

These checks are a flavor-level precondition layer over existing Agora approval and
evidence facts. They never transition work and never replace Core lifecycle gates.
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from agora_ai_sdlc.depth_profiles import asset_root
from agora_ai_sdlc.independent_review import ReviewPolicyError, resolve_profiles
from agora_ai_sdlc.profile_activation import adoption_profiles

SCHEMA = "agora-ai-sdlc/review-policy/v1"
REVIEW_IDS = (
    "business-review",
    "architecture-review",
    "security-compliance-review",
    "quality-review",
    "operational-readiness-review",
)


class EnterpriseReviewError(ValueError):
    """Stable validation error for enterprise review policy/evaluation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class ReviewRequirement:
    id: str
    mandatory: bool
    required_approval_roles: tuple[str, ...]
    required_evidence_types: tuple[str, ...]
    independent_review_profiles: tuple[str, ...]


@dataclass(frozen=True)
class ReviewPolicy:
    id: str
    adoption_profile: str
    reviews: tuple[ReviewRequirement, ...]

    def review(self, review_id: str) -> ReviewRequirement:
        for review in self.reviews:
            if review.id == review_id:
                return review
        raise EnterpriseReviewError("enterprise-review.review_unknown", f"unknown review {review_id!r}")


@dataclass(frozen=True)
class ReviewFact:
    id: str
    approval_roles: tuple[str, ...] = ()
    evidence_types: tuple[str, ...] = ()
    independent_review_profiles: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewResult:
    id: str
    mandatory: bool
    status: str
    blockers: tuple[dict[str, str], ...]

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "mandatory": self.mandatory,
            "status": self.status,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class ReviewBundleResult:
    profile: str
    allowed: bool
    reviews: tuple[ReviewResult, ...]

    def snapshot(self) -> dict:
        return {
            "schema": "agora-ai-sdlc/review-bundle-result/v1",
            "profile": self.profile,
            "allowed": self.allowed,
            "reviews": [review.snapshot() for review in self.reviews],
        }


def _strings(value: object, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise EnterpriseReviewError("enterprise-review.type", f"{field!r} must be a list of non-empty strings")
    if not allow_empty and not value:
        raise EnterpriseReviewError("enterprise-review.type", f"{field!r} must not be empty")
    if len(set(value)) != len(value):
        raise EnterpriseReviewError("enterprise-review.duplicate", f"{field!r} contains duplicates")
    return tuple(value)


def load_policy(profile_id: str) -> ReviewPolicy:
    """Load and validate the review policy bound to one adoption profile."""

    profiles = adoption_profiles()
    if profile_id not in profiles:
        raise EnterpriseReviewError("enterprise-review.profile_unknown", f"unknown adoption profile {profile_id!r}")
    path = asset_root("profiles") / "reviews" / f"{profile_id}.yaml"
    if not path.is_file():
        raise EnterpriseReviewError(
            "enterprise-review.policy_missing",
            f"review policy for adoption profile {profile_id!r} is not packaged",
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise EnterpriseReviewError("enterprise-review.schema", f"invalid review policy schema in {path.name}")
    expected = {"schema", "id", "adoption_profile", "reviews"}
    if set(data) != expected or data.get("id") != profile_id or data.get("adoption_profile") != profile_id:
        raise EnterpriseReviewError("enterprise-review.fields", f"invalid review policy identity for {profile_id!r}")
    raw_reviews = data["reviews"]
    if not isinstance(raw_reviews, list) or len(raw_reviews) != len(REVIEW_IDS):
        raise EnterpriseReviewError(
            "enterprise-review.review_set",
            f"review policy must declare exactly {len(REVIEW_IDS)} enterprise reviews",
        )

    parsed: list[ReviewRequirement] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_reviews):
        if not isinstance(raw, dict):
            raise EnterpriseReviewError("enterprise-review.type", f"reviews[{index}] must be a mapping")
        review_fields = {
            "id",
            "mandatory",
            "required_approval_roles",
            "required_evidence_types",
            "independent_review_profiles",
        }
        if set(raw) != review_fields:
            raise EnterpriseReviewError("enterprise-review.fields", f"reviews[{index}] has invalid fields")
        review_id = raw["id"]
        if review_id not in REVIEW_IDS:
            raise EnterpriseReviewError("enterprise-review.review_unknown", f"unknown review {review_id!r}")
        if review_id in seen:
            raise EnterpriseReviewError("enterprise-review.duplicate", f"duplicate review {review_id!r}")
        seen.add(review_id)
        if not isinstance(raw["mandatory"], bool):
            raise EnterpriseReviewError("enterprise-review.type", f"{review_id}.mandatory must be boolean")
        approvals = _strings(raw["required_approval_roles"], f"{review_id}.required_approval_roles")
        evidence = _strings(raw["required_evidence_types"], f"{review_id}.required_evidence_types")
        independent = _strings(
            raw["independent_review_profiles"],
            f"{review_id}.independent_review_profiles",
            allow_empty=True,
        )
        if independent:
            try:
                resolve_profiles(independent)
            except ReviewPolicyError as error:
                raise EnterpriseReviewError("enterprise-review.independent_profile", str(error)) from error
        parsed.append(
            ReviewRequirement(
                id=review_id,
                mandatory=raw["mandatory"],
                required_approval_roles=approvals,
                required_evidence_types=evidence,
                independent_review_profiles=independent,
            )
        )

    if set(seen) != set(REVIEW_IDS):
        missing = sorted(set(REVIEW_IDS) - seen)
        raise EnterpriseReviewError(
            "enterprise-review.review_set",
            f"review policy is missing reviews: {', '.join(missing)}",
        )
    return ReviewPolicy(profile_id, profile_id, tuple(parsed))


def available_policies() -> tuple[str, ...]:
    root = asset_root("profiles") / "reviews"
    if not root.is_dir():
        return ()
    return tuple(path.stem for path in sorted(root.glob("*.yaml")))


def evaluate(policy: ReviewPolicy, facts: tuple[ReviewFact, ...]) -> ReviewBundleResult:
    """Evaluate normalized Core approval/evidence facts against one policy bundle."""

    by_id: dict[str, ReviewFact] = {}
    for fact in facts:
        if fact.id not in REVIEW_IDS:
            raise EnterpriseReviewError("enterprise-review.fact_unknown", f"unknown review fact {fact.id!r}")
        if fact.id in by_id:
            raise EnterpriseReviewError("enterprise-review.fact_duplicate", f"duplicate review fact {fact.id!r}")
        by_id[fact.id] = fact

    results: list[ReviewResult] = []
    for requirement in policy.reviews:
        fact = by_id.get(requirement.id)
        if fact is None:
            if requirement.mandatory:
                results.append(
                    ReviewResult(
                        requirement.id,
                        True,
                        "BLOCKED",
                        (
                            {
                                "code": "enterprise-review.missing",
                                "message": f"mandatory review {requirement.id!r} has no approval/evidence fact",
                            },
                        ),
                    )
                )
            else:
                results.append(ReviewResult(requirement.id, False, "OPTIONAL_MISSING", ()))
            continue

        blockers: list[dict[str, str]] = []
        missing_roles = sorted(set(requirement.required_approval_roles) - set(fact.approval_roles))
        if missing_roles:
            blockers.append(
                {
                    "code": "enterprise-review.approval",
                    "message": f"missing approval roles: {', '.join(missing_roles)}",
                }
            )
        missing_evidence = sorted(set(requirement.required_evidence_types) - set(fact.evidence_types))
        if missing_evidence:
            blockers.append(
                {
                    "code": "enterprise-review.evidence",
                    "message": f"missing evidence types: {', '.join(missing_evidence)}",
                }
            )
        missing_independent = sorted(
            set(requirement.independent_review_profiles) - set(fact.independent_review_profiles)
        )
        if missing_independent:
            blockers.append(
                {
                    "code": "enterprise-review.independent",
                    "message": f"missing independent-review decisions: {', '.join(missing_independent)}",
                }
            )

        status = "BLOCKED" if blockers and requirement.mandatory else "OPTIONAL_INCOMPLETE" if blockers else "PASS"
        results.append(ReviewResult(requirement.id, requirement.mandatory, status, tuple(blockers)))

    frozen = tuple(results)
    return ReviewBundleResult(
        policy.id,
        allowed=not any(result.mandatory and result.status == "BLOCKED" for result in frozen),
        reviews=frozen,
    )
