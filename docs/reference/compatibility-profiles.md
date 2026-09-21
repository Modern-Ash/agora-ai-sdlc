# Compatibility profiles

Agora AI-SDLC keeps one provider-neutral internal vocabulary and projects it into public external method presentations through versioned compatibility profiles. A compatibility profile is a conformance target, not a runtime dependency and not a claim of affiliation, endorsement or certification.

The contract is agora-ai-sdlc/compatibility-profile/v1. Its checked-in JSON Schema is [compatibility-profile-v1.schema.json](../../contracts/conformance/compatibility-profile-v1.schema.json).

## Canonical elements

The compatibility layer uses five stable conceptual elements:

| Canonical element | Meaning |
| --- | --- |
| readiness | pre-delivery organizational/technical readiness and bootstrap capability |
| intent | high-level purpose/ideation input that drives planning |
| inception | elaboration and decomposition before construction |
| construction | design, implementation and verification |
| operations | deployment, observability and operational action |

These are compatibility elements, not a second Core lifecycle. In particular, Method Pack 0.2.0 can remove readiness and intent as lifecycle states while the compatibility vocabulary remains stable: they continue to describe capabilities and artifacts used by presentation profiles.

The terminal Core state completed is intentionally absent because it is an Agora recording state, not an external method phase.

## AWS-original profile

profiles/compatibility/aws-original/profile.yaml represents only the public AWS method definition and public blog material. It presents three phases:

Inception -> Construction -> Operations

The intent canonical element is grouped into the Inception presentation because Intent is the method's starting input to Inception. readiness is deliberately not presented as an AWS phase.

The profile declares method capabilities as required, optional or unsupported. This is a target contract for the later conformance engine; presence in the file does not mean the current release already passes every capability.

## LG-enterprise profile

profiles/compatibility/lg-enterprise/profile.yaml represents only behavior described publicly for the LG CNS enterprise offer. Its presentation is:

Initialization -> Ideation -> Inception -> Construction -> Operation

The two leading stages are projections, not extra AWS-original phases:

- Initialization maps to Agora readiness.
- Ideation maps to Agora intent.
- The remaining stages map directly to Inception, Construction and Operations.

Enterprise capabilities such as review gates, cross-repository impact, change/configuration management, domain knowledge, test design and code review are declared as compatibility targets. Proprietary or non-public LG implementation details are not modeled.

## Validation rules

Runtime validation is local and deterministic:

- schema, id and semantic version must be valid;
- source basis must be public, with HTTPS references;
- profiles must explicitly state affiliation: false and runtime_dependency: false;
- presentation stage ids must be unique;
- every maps_from entry must reference a known canonical element;
- one canonical element cannot be projected into two presentation stages;
- required, optional and unsupported capability sets must be pairwise disjoint;
- provider, model, cloud, SCM and agent-runtime neutrality must all be declared true.

Stable failure codes are exposed through CompatibilityProfileError.code.

## Neutrality and claims

Compatibility assets do not require AWS services, LG software, Bedrock, a specific LLM, GitHub, GitLab, or any particular agent runtime. The source URLs establish the public material used to define the profile; they are not fetched at runtime.

Agora AI-SDLC is not affiliated with or endorsed by AWS or LG CNS. Conformance and Marketplace claims must be generated from implementation evidence in later conformance work rather than inferred merely from the existence of these profiles.
