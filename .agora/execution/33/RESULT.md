---
issue: 33
status: implemented
implemented_at: 2026-09-20
implementer: Codex
review: pending-independent
---
# Result: Enterprise profile with signed registry consumption

## Outcome

Added an Enterprise adoption profile that validates inherited organization policy separately from project customization and consumes signed organization registries as immutable project-local snapshots through supported Agora Core APIs.

## Delivered

- Organization registry source/version, Ed25519 trust threshold, provider allowlist, budget ceilings, required metrics, and exception-record contract.
- Pure signature preview plus project-scoped public trust bootstrap and Core install with persisted SHA-256 provenance.
- Read-only upgrade preview, reviewed-checksum guard, Core transactional apply/update history, and signed-forward recovery metadata.
- Credential-free executable install/upgrade sample with an ephemeral in-memory signer.
- Multi-project rollout, exception, revocation, upgrade, recovery, and deployment-responsibility documentation.

## Acceptance evidence

- Unknown signer, invalid signature, revoked key, and installed-but-unmanaged key all fail before registry installation.
- Core `SOURCE.md` records index/archive provenance, checksum, signers, threshold, and installed version.
- Config validation prevents project providers, budgets, or metrics from weakening organization policy; exception records grant no bypass.
- Upgrade preview writes nothing; reviewed-checksum conflicts and changed-version checksums fail without mutation; a bad archive leaves the prior snapshot intact; successful apply records `UPDATE.md`.

## Limits

- Registry publishing and cross-project rollout are external deployment responsibilities; releases must be append-only and immutable.
- Rollback is a newly signed higher release containing approved prior content, because Core rejects downgrades.
- This profile provides no hosted registry, fleet transaction, tenancy, users, or Control Plane.
- Independent review remains pending.

## Verification

Focused checks: `16 passed`; Ruff passed. Full verification: `446 passed, 2 skipped`; all phases passed with nine samples and wheel smoke test.
