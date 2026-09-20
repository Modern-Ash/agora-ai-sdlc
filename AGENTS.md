# AGENTS.md — Agora AI-SDLC agent contract

Shared contract for every coding agent (any runtime, provider or model). Tool-specific notes live in [docs/agents/](docs/agents/).

## 1. Purpose

Agora AI-SDLC is Modern Ash's vendor-neutral distribution of AI-first software-delivery practice, built on Agora Core. It ships a Method Pack, policy and integration profiles, templates, samples and product documentation. AWS AI-DLC is methodological inspiration only, never a dependency.

## 2. Repository scope and boundaries

| Product | Owns |
|---|---|
| Agora Core (`Modern-Ash/agora`) | Generic lifecycle engine, gates, roles, Tool Packs, durable state. Anything useful to Scrum, Kanban or Spec-Driven methods. |
| **Agora AI-SDLC (this repo)** | How Modern Ash implements AI-SDLC: Method Pack, profiles, policies, templates, samples, docs. |
| Agora Studio (`Modern-Ash/agora-studio`) | UI projections. Never parses Method Packs or writes `.agora/` directly. |
| Control Plane (future) | Multi-user/enterprise service. Not in the MVP. |

Details: [docs/repository-boundaries.md](docs/repository-boundaries.md), [docs/architecture.md](docs/architecture.md), [docs/terminology.md](docs/terminology.md).

## 3. Principles

AI-first, human-accountable · Clarification before execution · Evidence before transition · Independent review · Persistent context · Provider neutrality · Least privilege · Replaceable agents · Observable cost and quality · Reversible and auditable changes.

## 4. Hard prohibitions

- No mandatory dependency on any provider, model, cloud or agent product (no LLM SDKs, no provider-specific runtime code).
- No credentials, tokens or private keys in files, logs, fixtures or PRs.
- Do not invent commands, contracts, schemas or capabilities that do not exist. If unsure, ask via a clarification.
- Do not mix features with unrequested refactors.
- Do not overwrite or discard local or third-party changes; read a file before editing it.

## 5. Working from an issue

1. The GitHub issue plus `.agora/execution/<issue>/TASK.md` define scope. If the issue is not `ready` ([lifecycle](docs/development/issue-lifecycle.md)), stop and report.
2. Minimum reading: this file, the issue and its parent epic, `TASK.md`, the files listed under *Allowed paths*, and only the `.agora/context/` contracts the task names. Do not explore unrelated files.
3. Execution artifacts live in `.agora/execution/<issue>/` (`TASK.md`, `CLARIFICATION-*.md`, `TESTS.md`, `RESULT.md`, `REVIEW.md`), created from [.agora/templates/](.agora/templates/). Flow: [docs/development/task-execution.md](docs/development/task-execution.md).
4. Edit only *Allowed paths*. Anything in *Forbidden changes* needs a clarification, not a workaround.

## 6. Ambiguity

Do not decide architecture, contracts or scope implicitly. Record a `CLARIFICATION` (question, options, recommendation), stop the affected work, and wait for the accountable human. Decisions of lasting weight become an ADR in [docs/decisions/](docs/decisions/).

## 7. Verification

- During development run focused checks for the touched area; run the full validation before opening the PR ([testing](docs/development/testing.md)).
- Record exact commands, results, omitted checks and reasons in `TESTS.md`.
- Validation command: `uv run python scripts/verify_all.py` (single entry point; see [CONTRIBUTING.md](CONTRIBUTING.md)). It runs lint, format, tests, links, manifest, packs, samples and a wheel smoke test. Packs and samples phases currently report nothing to validate. Do not claim other checks that were not executed.
- Add failure-path tests for behavior that must fail closed.

## 8. Security

Least privilege; fail closed when required metadata is missing; never infer provider independence from model names; never persist provider credentials; keep logs secret-safe.

## 9. Commits and pull requests

Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`), one issue per branch/PR, branch `<type>/<issue>-<slug>`. PR body links the issue, lists acceptance criteria status, tests and remaining risks ([pull-requests](docs/development/pull-requests.md)). No force-push, no self-merge.

## 10. Review

Critical work needs independent review: a different session, and where policy demands it a different runtime or provider, from the implementer. The reviewer reads `TASK.md`, the diff, changed files and test evidence, and writes `REVIEW.md`; it does not re-implement.

## 11. Definition of Done

All acceptance criteria met and evidenced; tests recorded; `RESULT.md` complete; review verdict `approved` or `approved-with-observations`; no scope creep; no secrets; docs updated. Full list: [definition-of-done](docs/development/definition-of-done.md). Close an issue only after verifying its criteria.

## 12. Roles and efficiency

Planner, Implementer and Reviewer are separate responsibilities ([docs/agents/](docs/agents/)). Keep tasks small and sessions disposable; budgets in [token-efficiency](docs/development/token-efficiency.md). Split any task that exceeds its budget before implementing.
