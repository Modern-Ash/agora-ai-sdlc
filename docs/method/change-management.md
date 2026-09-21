# Governed change and configuration management

Agora AI-SDLC models enterprise change control as a traceable artifact chain rather than a provider-specific ticketing workflow:

`Change Request -> Approved Change Plan -> Configuration Delta -> Release Evidence / Rollback Linkage`

The contracts are local, deterministic, and provider-neutral. They do not deploy software or mutate an external configuration service.

## Change request

A `change-request` artifact records:

- accountable requester;
- reason;
- scope;
- initial risk;
- trace to a Unit of Work or approved impact analysis.

## Change plan

A `change-plan` artifact records:

- the originating change request;
- optional Level-N execution plan;
- ordered implementation steps;
- release targets;
- rollback-plan reference;
- exact-revision human approval.

An approved change plan is valid only when `approved-revision` matches the current artifact revision. Editing the plan invalidates prior approval.

## Configuration delta

A `configuration-delta` artifact records non-secret configuration/resource changes:

- logical key;
- before/after descriptors;
- resource;
- release evidence references;
- rollback linkage references.

Secret-bearing keys and secret-like values are rejected. Release and rollback references must be credential-free opaque/local references.

## Traceability

The generic artifact graph supports:

`Unit / Impact Analysis -> Change Request -> Change Plan -> Configuration Delta`

The change-management validator then proves that the supplied request, plan, and delta are the same chain and that the plan is currently approved.

## Release and rollback evidence

Release evidence and rollback linkage are references, not embedded provider payloads. Example forms include:

- `evidence:release/payments-2026.09.21`
- `repo://ops/rollback/recurring-payments.md`

The contracts do not require GitHub, GitLab, Jira, AWS, or any deployment vendor.
