# Regulated profile

The Regulated profile composes the Enterprise baseline, `regulated` depth, Agora Core signed lifecycle actions, the `regulated` independent-review policy, evidence-retention metadata, and complete observed model/runtime provenance. It adds technical controls for higher-assurance delivery; it does **not** certify a project, organization, product, or deployment against any law, regulation, or industry standard.

## Control contract

`profiles/regulated/profile.yaml` is the declarative contract. The critical actions listed there require actors with active Core Ed25519 identities. Every required swarm role must have such an identity before regulated use, and `product-owner` and `quality-reviewer` must be human actors. Architect, builder, operator, and Product Owner roles cannot share an actor with the Quality Reviewer.

Call `assess_assignments` before assignment or use and `assign_actor` for profile-aware assignment. Call `require_ready_swarm` before any regulated operation. These checks fail before Core mutation. The profile does not add lifecycle states or rewrite Core actor records.

For critical lifecycle changes, use Core's `prepare_*` operation, sign the canonical authorization payload with the actor's current key, then call `apply_signed_action`. Core verifies the Ed25519 signature, current actor key, exact action parameters, and precondition digest. Missing signatures and stale preconditions fail in Core. The flavor never accepts a boolean or caller assertion as proof of signing.

Production keys must be generated, protected, rotated, revoked, and recovered under the organization's approved key-management process. Ephemeral quickstart or test keys are evaluation material only and are not production custody guidance. Private keys must never be committed to the project, exception records, evidence metadata, or logs.

## Segregation and review

Role segregation is evaluated on canonical scoped Core actor references. It is checked both for proposed assignments and the complete current swarm, so bypassing the assignment helper does not make later regulated use valid. The four declared role combinations, human approval roles, signed actions, and complete provenance are non-waivable profile controls.

Critical artifact review uses the existing `regulated` independent-review profile. It requires a distinct actor and provider at observed provenance trust plus a non-waivable human final review. An approval in Core remains necessary where the Method Pack gate requires it; a review-policy result does not manufacture a Core approval.

## AI execution provenance

`evaluate_ai_execution` requires observed values for runtime, runtime version, provider, model, selection reason, and fallback selection. Declared or unavailable values block execution. Core 0.8 session records do not observe every one of these fields, so a reviewed runtime adapter must supply the missing observations through the model-provenance contract. The profile does not infer provider identity from a model name and offers no exception to this control.

## Audit metadata

Exceptions are allowed only for `data-handling`, `retention-period`, and `operational-control`. Each record requires a slug id, reason, configured Governance Owner identity and role, creation and expiry timestamps, and an evidence reference. The lifetime is at most 30 days, and expired records fail closed. `record_exception` writes a new JSON record under `.agora/regulated/exceptions/` with exclusive creation; an id cannot be overwritten.

Evidence retention records require an evidence reference, owner, classification, policy, recording time, future retention deadline, and disposition. `prepare_evidence` validates and records this metadata before asking Core to prepare the action, so an audit-write failure cannot leave a signable action without retention metadata. A later Core validation failure can leave an immutable record of the unsuccessful preparation attempt; retry with a new id. Audit paths are constrained to the project even when filesystem links are present. Records contain metadata and references, not evidence contents or credentials.

Organization policy is the source of configured exception authorizers and retention schedules. Changes require a new record; do not edit an existing JSON audit record. Git protection and external archival can make repository records harder to remove, but this package does not provide WORM storage, legal hold enforcement, clock attestation, key custody, identity proofing, OS isolation, network controls, backup policy, or records disposition.

## Executable scenario

```console
agora-ai-sdlc run-sample regulated
```

The offline sample uses ephemeral in-memory signing keys and drives a complete `readiness -> completed` lifecycle in which every critical action is prepared, signed and applied through Agora Core. It also shows an unsigned mutation, a non-human product owner and a builder/quality-reviewer combination rejected, declared provenance blocked while observed provenance is allowed, an unauthorized and a non-waivable exception rejected, and evidence retention metadata recorded. It ends with `agora validate`.

## Customer responsibilities

Customers must map these controls to their actual obligations with qualified security, legal, privacy, and compliance owners. They remain responsible for risk assessment, control design, identity lifecycle, organization-managed keys, trustworthy runtime observations, retention periods, evidence preservation and deletion, repository access, branch protection, infrastructure isolation, monitoring, incident response, independent audits, and any required filings or attestations.

Passing profile checks means only that the declared technical contract was satisfied for the evaluated repository state. It is not evidence of regulatory certification or legal compliance.
