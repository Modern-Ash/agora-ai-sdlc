---
issue: 34
status: implemented
implemented_at: 2026-09-20
implementer: Codex
review: pending-independent
---
# Result: Regulated profile and segregation controls

## Outcome

Added a fail-closed Regulated adoption profile that composes existing depth, independent-review and provenance contracts with Agora Core actor identities and signed lifecycle actions.

## Delivered

- Declarative critical actions, mandatory human roles, non-combinable roles, non-waivable controls, observed provenance requirements, and audit-record fields.
- Assignment and swarm preflight over public Core actor/swarm records, including active Ed25519 identity checks.
- Signed transition/evidence adapters that delegate preparation, verification, stale-precondition handling and mutation to Core.
- Complete observed AI execution provenance evaluation, including runtime version, selection reason and fallback state.
- Explicit Governance Owner-authorized exceptions with maximum lifetime and no bypass for signature, segregation, human approval or provenance controls.
- Immutable project-local exception and evidence-retention metadata with path-confinement and credential rejection.
- Operational documentation separating package controls from customer compliance responsibilities and disclaiming certification.

## Limits

- Regulated conformance requires callers to use profile preflight before operations; direct Core calls still enforce actor authentication but do not know flavor-specific role pairs or metadata rules.
- Repository JSON records are exclusive-create audit metadata, not WORM storage, legal-hold infrastructure, clock attestation, or an external archive.
- Organization policy must provide trusted exception-authorizer mappings and retention schedules.
- Core session metadata alone does not observe every required provenance field; a reviewed adapter must supply those observations.
- Production key custody, identity proofing, infrastructure isolation, evidence preservation/disposition, legal interpretation and certification remain customer responsibilities.
- Independent review remains pending.

## Verification

Focused checks: `93 passed`; Ruff and format passed. Full verification: `498 passed, 2 skipped`; all phases passed with ten samples and wheel smoke test.
