# Cross-repository impact analysis

The `impact-analysis` artifact captures declared change impact across multiple repositories before implementation. It is provider-neutral and does not require GitHub, GitLab, Bitbucket, a graph database, or any remote discovery service.

## Scope and traceability

Every impact analysis is scoped to one Unit of Work and may additionally bind to:

- a Level-N Plan;
- one or more Bolt Plans.

Those references must also appear in the generic `traces-to` field, so ordinary Agora artifact traceability can connect:

`Intent -> Unit -> Plan -> Bolt Plan -> Impact Analysis`

The impact artifact does not replace Unit/Plan/Bolt semantics; it records the cross-repository blast radius for them.

## Repository identifiers

Repositories use provider-neutral lowercase slugs such as:

`payments-api`

An optional `ref` may carry an opaque URI-like locator such as:

`repo:payments-api`

The validator does not interpret provider-specific hosts or credentials.

## Components and contracts

Affected components/modules are bound to a declared repository and state the expected change.

Contracts use a closed type vocabulary:

- `api`
- `event`
- `schema`

Each contract records its owning repository and expected change.

## Dependencies and unknowns

Every dependency records:

- source repository;
- target repository;
- direction: `inbound`, `outbound`, `bidirectional`, or `unknown`;
- status: `known` or `unknown`;
- optional reason.

An unknown dependency must include a reason, and the artifact must also keep unresolved unknowns explicit. Unknowns are not treated as absence of impact.

## Approval

Impact analysis has exact-revision approval semantics:

- `pending`
- `approved`
- `rejected`

An approved artifact requires:

- `approved-by`;
- `approved-revision` equal to the current artifact revision;
- the approver to be in the declared reviewers;
- at least one reviewer distinct from all declared owners.

Changing the artifact revision invalidates the previous approval.

## Enterprise review integration

Enterprise and regulated architecture review policies require the normalized evidence type:

`approved-impact-analysis`

The helper `enterprise_review_evidence()` returns this evidence type only after the current impact-analysis revision passes approval validation.

This keeps the relationship explicit:

`approved impact analysis -> enterprise architecture review evidence -> Core lifecycle gate`

Core remains authoritative for lifecycle transitions.

## Offline guarantee

Validation is local and deterministic. The artifact records declared repositories and dependencies; this issue does not perform network discovery or mutate external repositories.
