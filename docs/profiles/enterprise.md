# Enterprise profile

Enterprise composes the Starter baseline for multiple repositories and teams. It consumes an organization registry as a signed, project-scoped snapshot and validates each project's provider choices, budget limits, and metric exports against explicit organization policy. Agora Core remains the registry, trust, checksum, provenance, and transactional update authority.

This is a file- and automation-based rollout model. It does not provide users, tenancy, a hosted registry, centralized configuration, or multi-user Studio.

## Policy boundary

The `agora-ai-sdlc/enterprise-config/v1` document has two required sections:

| Organization policy | Project customization |
| --- | --- |
| Registry id, HTTPS or local index source, pinned release version, signature threshold, public trust keys | Project id |
| Allowed provider identifiers | Provider subset |
| Budget ceilings by dimension | Equal-or-lower limits for every dimension |
| Required exported metric identifiers | Required metrics plus optional project metrics |
| Exception record requirements from the profile manifest | Time-bounded exception requests; never an automatic bypass |

Unknown fields fail validation. URLs must be credential-free HTTPS without query or fragment data. Public-key files must contain Ed25519 public keys; private keys and provider credentials do not belong in configuration, project state, logs, or fixtures.

The profile validates declared provider, budget, and metric configuration. Runtime eligibility remains enforced by the data, independent-review, and runtime-selection policies; metric collection remains a deployment responsibility using the observability profile. A config declaration is not evidence that a provider or exporter actually ran.

## Install

`preview_install(config, project)` validates both policy layers and asks Core to verify the selected signed release against the configured threshold. It returns the release checksum and verified key ids without writing. Review that output before calling `install(config, project)`.

Apply registers only public trust keys in project scope, then calls Core `install_registry` with a required signature threshold. Core verifies the signature and archive SHA-256, extracts safely, validates the registry, and atomically places the snapshot at `.agora/registries/<id>/`. `SOURCE.md` records the index, resolved archive, release version, SHA-256, verified key ids, threshold, and installation time.

A revoked matching key fails closed even if configuration still names it. A conflicting key id, an installed key for the registry absent from organization policy, an unknown signer, invalid signature, malformed archive, or checksum mismatch also fails. Trust-key rotation must update the reviewed policy and project trust records together. Organization registry publishers must treat released versions as append-only and immutable.

## Upgrade and recovery

`preview_upgrade(config, project)` is read-only and reports the current and selected versions, selected checksum, signature result, and recovery point. `apply_upgrade(..., reviewed_checksum=...)` refuses a checksum different from the current preview and delegates apply to Core. Core rechecks the index and signature, downloads and verifies the archive before replacement, restores its temporary backup if replacement fails, and records the completed transition under `updates/<id>/UPDATE.md`.

Core intentionally rejects downgrades. Recovery therefore uses a **signed forward release**: publish a higher version containing the last approved content, preview its checksum, approve it, and apply it normally. Preserve the prior version and checksum from the preview/update record for that decision. Do not edit `SOURCE.md`, `UPDATE.md`, or registry snapshot files by hand.

## Exceptions

An exception record requires `id`, `policy`, `reason`, `approved_by`, timezone-qualified `expires_at`, and `evidence`. Recording an exception does not weaken validation. The governance owner must issue a separately reviewed, time-bounded organization-policy revision that permits the exceptional value, retain the decision evidence, and remove the allowance when it expires. Emergency edits to generated Core records are not an exception mechanism.

## Multi-project rollout

1. Publish immutable registry archives and an append-only signed index over HTTPS.
2. Distribute reviewed Enterprise config and public trust roots through the organization's normal repository controls.
3. Run preview, review its version/checksum/signers, and apply independently in each project.
4. Commit the project-local config and `.agora` snapshot/provenance according to repository policy.
5. Audit projects for the approved version and exported metrics with external CI automation.
6. Revoke compromised keys in every affected project, rotate to a new key id, and publish a newly signed release.

Rollout automation must report per-project success and failure; partial fleet rollout is possible because there is no Control Plane transaction across repositories.

The credential-free [Enterprise sample](../../samples/enterprise/README.md) creates an ephemeral signer in memory, installs version 1, previews version 2, applies it, and checks provenance and update history.
