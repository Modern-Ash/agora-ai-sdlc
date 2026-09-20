---
issue: 30
status: implemented
implemented_at: 2026-09-20
implementer: Codex
review: approved
---
# Result: GitLab and Jira follow-on profiles

## Outcome

Added GitLab delivery and Jira work-management profiles over Agora Core's reviewed CLI adapters. Both reuse neutral issue capabilities, default to read-only, require explicit grants plus confirmation for writes, and preserve Agora Core as lifecycle authority.

## Delivered

- Profile manifests for GitLab issues/MRs/pipelines and Jira work items/transitions.
- Provider-bound translators producing immutable neutral work-item and delivery observations.
- GitLab/Jira fixtures with equivalent normalized open work-item outcomes.
- Append-only reconciliation with idempotent retries and conflict rejection.
- Stable policy, unsupported-operation, malformed-fact, and delivery-blocker errors.
- Credential-free executable samples for each integration.
- Reference documentation covering prerequisites, permissions, source of truth, reconciliation, failures, and unsupported operations.

## Acceptance evidence

- No Method Pack file changed; a test also rejects `gitlab` or `jira` branches in Method Pack files.
- Provider response fields are read only inside the GitLab/Jira translation boundary.
- Fixtures normalize to the same `{state: open, terminal: false}` outcome.
- Unsupported Core operations fail with explicit `<provider>.operation.unsupported` codes.
- Permission and external-failure cases are covered independently.

## Limits

- No provider CLI is launched and no live account is required by the samples.
- GitLab issue creation, MR decisions/merge, and pipeline trigger remain unsupported because Core's reviewed adapters deliberately omit them.
- Jira supplies work management only; it cannot represent code review, CI, or Agora lifecycle transitions.
- Custom Jira statuses require an explicit reviewed state mapping before ingestion.
- Independent review requested changes for Jira adapter fidelity, reconciliation identity, and exact external-reference bounds. Every finding and final observation was corrected with regression tests; the final verdict is `approved`.

## Verification

Focused checks: `37 passed`; Ruff passed. Full verification: `394 passed, 2 skipped`; all phases passed, including six samples and wheel smoke test. Exact commands are recorded in `TESTS.md`.
