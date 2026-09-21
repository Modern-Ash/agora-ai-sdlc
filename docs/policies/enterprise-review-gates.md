# Enterprise review gates

The enterprise review bundle is a flavor-level policy layer over existing Agora approvals, evidence, and independent-review decisions. It does not transition work and does not replace Agora Core lifecycle gates.

## Review set

The bundle defines five review controls:

- business review
- architecture review
- security/compliance review
- quality review
- operational readiness review

Each review policy declares whether the review is mandatory, which approval roles are required, which evidence types must be present, and which independent-review profiles must already have passed.

## Adoption profiles

Three packaged policies are available:

- **starter**: business, quality, and operational readiness are mandatory; architecture and security/compliance can remain optional for small-team delivery.
- **enterprise**: all five reviews are mandatory; architecture review also requires `approved-impact-analysis` evidence.
- **regulated**: all five are mandatory, governance-owner participation is added where configured, sensitive reviews require the existing regulated independent-review policy, and architecture review requires `approved-impact-analysis` evidence.

The policy files are under profiles/reviews/.

## Existing Agora primitives

The evaluator consumes normalized facts corresponding to existing Core concepts:

- approval roles
- evidence types
- independent-review decisions

Independent-review profile names are validated against agora_ai_sdlc.independent_review. This keeps producer/reviewer separation, human-final review, and regulated provenance semantics in one place.

## Fail-closed behavior

Missing mandatory reviews block. Missing required approvals, evidence, or independent-review decisions also block. Optional reviews may be absent without blocking a Starter project.

The evaluator is read-only and offline. It never invokes a reviewer tool, LLM, provider API, or cloud service.

## Example

A caller can normalize current project facts and evaluate them before requesting a Core transition:

```python
from agora_ai_sdlc.enterprise_reviews import ReviewFact, evaluate, load_policy

policy = load_policy("enterprise")
result = evaluate(
    policy,
    (
        ReviewFact("business-review", ("product-owner",), ("business-decision",), ()),
        # additional review facts...
    ),
)

if not result.allowed:
    raise RuntimeError(result.snapshot())
```

Core remains the lifecycle authority. The review bundle only answers whether the enterprise policy prerequisites are satisfied.
