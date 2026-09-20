---
issue: 42
status: documented
commit: pending
pull_request: pending
updated_at: 2026-09-20
---
# Result: Vendor-neutral reference architecture and shared responsibility

## Status

Documentation and verification complete; independent review pending.

## Concise summary

Published a neutral logical architecture for local, CI, and self-managed enterprise operation, plus a control-by-control responsibility model separating Agora enforcement and flavor validation from deployment evidence and customer/provider operation.

## Files modified

Two commercial reference documents, the commercial index, documentation contract tests, and issue execution records.

## Decisions made

- Kept the primary diagram technology-neutral and isolated vendor names to an explicitly optional mapping appendix.
- Treated the CLI as sufficient and Studio as optional presentation over Core projections, including current compatibility gaps.
- Assigned identity, credentials, isolation, residency, provider/model terms, backups, and incident response to customer deployment controls.
- Described Core enforcement only where existing contracts support it and labeled external observations as supplied evidence rather than proof of infrastructure effectiveness.
- Used signed forward releases and per-project reporting for enterprise recovery because no fleet transaction or Control Plane exists.

## Criteria satisfied

- Core, flavor, Studio, external runtime/tool, Git, and project-state boundaries match repository contracts.
- Workstation, CI, and self-managed enterprise deployment patterns are documented.
- Runtime, provider, integration, registry, monitoring, and presentation replacement points are explicit.
- Security enforcement, validation, evidence, and deployment responsibility are distinguished.
- Runtime, integration, registry, partial-rollout, Studio, backup, and compromise failure/recovery paths are documented.
- AWS, Azure, GCP, and on-premises examples are optional and appear after the neutral architecture.

## Tests run

Focused documentation tests, Ruff lint/format checks, and full repository verification.

## Results

Focused: `9 passed`. Full: `526 passed, 2 skipped`; all phases passed, including eleven samples and installed-wheel self-test.

## Deviations

No live cloud architecture or customer-specific topology was produced because the issue requires a vendor-neutral reference and cloud-specific examples only.

## Remaining risks

Independent architecture/security and editorial review remain pending. The examples do not validate a customer's IAM, network, data-residency, backup, incident, provider-contract, or compliance design.

## Pending work

Independent review, PR creation, and repository CI. Marketplace-ready commercial copy remains #43.

## Commit and pull request

Pending.
