---
issue: 9
epic: 1
title: Resolve repository name and publish canonical identity
repository: Modern-Ash/agora-ai-sdlc
base_commit: ef638fe
status: planning
risk: low
context_size: small
budget:
  max_input_tokens: 10000
  max_output_tokens: 5000
planner: claude-code
created_at: 2026-09-20
---
# Task: Resolve repository name and publish canonical identity

## Objective
Publish the canonical identity `agora-ai-sdlc` (no trailing dot) in tracked docs.

## Business outcome
Contributors clone and reference the repo without the dotted-name anomaly.

## Current state
- GitHub rename already done and verified (`Modern-Ash/agora-ai-sdlc`); local `origin` correct.
- No `README.md`, no package metadata yet (`pyproject.toml` belongs to #10).
- Existing docs contain no dotted-name references (checked in PR #44).

## Required inputs
AGENTS.md, issue #9, `gh repo view`, PR #44 merged (or branch based on it).

## Allowed paths
`README.md`, `docs/decisions/ADR-0001-repository-name.md` (optional), `docs/**` link fixes.

## Forbidden changes
Package metadata / `pyproject.toml` (#10), code, CI, other issues' files.

## Functional requirements
- Create minimal `README.md` with canonical name and clone command (HTTPS and `gh repo clone`, valid on Linux/macOS/Windows).
- Add a migration note that the former name ended with a dot and GitHub redirects the old URL (the only allowed mention of the dotted name).
- Record the naming decision (ADR or README note).

## Non-functional requirements
Relative links; English; no badges pointing to unverified services.

## Acceptance criteria
- [ ] Canonical GitHub name has no trailing punctuation.
- [ ] Documented clone command works on Linux, macOS and Windows.
- [ ] No tracked text references the old dotted name except the migration note.
- [ ] Issue history remains accessible after rename.

## Negative cases
Grep must flag any dotted-name occurrence outside the migration note.

## Focused verification
- `gh repo view --json nameWithOwner`.
- Repo-wide grep for the dotted name; relative-link check.
- Clone via the documented command into a temp directory (Linux; macOS/Windows by command inspection, document the limitation).
- `gh issue view 1` shows history intact.

## Full verification
None available yet (pipeline is #14); document as such in TESTS.md.

## Dependencies
None.

## Clarifications
- Q1: Should the migration note be permanent or removed after a release? Recommendation: keep until first published package.
- Q2: Close #9 automatically when merged? Recommendation: yes, only after criteria verified.

## Completion evidence
TESTS.md with the commands above; RESULT.md; REVIEW.md.
