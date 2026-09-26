# Architecture

Decisions: [ADR-0001](decisions/ADR-0001-separate-flavor-repository.md), [ADR-0002](decisions/ADR-0002-no-embedded-llm-sdk.md), [ADR-0003](decisions/ADR-0003-provider-neutral-naming.md). Product: [vision](product/vision.md), [positioning](product/positioning.md).

Conceptual architecture of the Agora AI-SDLC flavor. Nothing here is implemented yet unless stated; see [product-scope.md](product-scope.md). Boundaries: [repository-boundaries.md](repository-boundaries.md). Terms: [terminology.md](terminology.md).

## Layers

```mermaid
flowchart TB
  Studio[Agora Studio - projections] --> Core
  CP[Future Control Plane] -.-> Core
  Flavor[Agora AI-SDLC flavor] --> Core[Agora Core]
  Core --> Runtimes[External runtimes/agents]
  Core --> Tools[Tool Packs / integrations]
```

- **Core** owns the lifecycle engine, gate enforcement, durable state and Tool Pack operations.
- **Flavor** (this repo) composes Core capabilities into AI-SDLC: manifest, Method Pack, policies, profiles, templates, samples. It never duplicates lifecycle logic.
- **Studio** renders Core projections; it holds no lifecycle policy.
- **Runtimes** (Codex, Claude Code, OpenCode, Ollama, ...) are replaceable actors; no runtime is required. They split into *agent runtimes* (repository-aware hosts: Claude Code, Codex, OpenCode) and *model runtimes* (Ollama), combined by `agora-ai-sdlc/runtime-binding/v2`; a model runtime alone never satisfies an agent-execution requirement. Legacy flat entries normalize deterministically; ambiguous ones fail with a typed diagnostic.
- Markdown and Git remain the project source of truth.

## Concepts

- **Flavor manifest** (`agora/flavor/v1`, issue #11): id, version, supported Core range, included packs, profiles, policies, required capabilities.
- **Method Pack**: declares lifecycle `readiness -> intent -> inception -> construction -> operations -> completed`, rework edges (`inception -> intent`, `construction -> inception`, `operations -> construction`), protocol and provider-neutral tools.
- **Roles**: authority and capability matrix; the accountable role holder is preserved when execution is delegated to AI.
- **Gates and evidence**: no transition without required evidence; missing evidence, unresolved clarification or missing approval fail closed.
- **Policies**: producer/reviewer separation, data classification and runtime eligibility, budgets and fallback, provenance.
- **Profiles**: the implemented Starter, Enterprise, Modernization and Regulated adoption profiles compose shared assets without forking Core. Enterprise delegates registry trust and transactions to Core; Modernization evaluates additional artifact/evidence obligations before delegating transitions; Regulated delegates actor identity, signatures, stale preconditions and lifecycle mutation to Core while the flavor owns segregation, provenance completeness and exception/retention metadata.
- **Integrations**: the implemented GitHub and GitLab delivery, Jira work-management, generic CI/CD, security-finding, and operational-evidence profiles compose Core's provider-neutral Tool Pack, evidence, control-band, and structured-finding operations. External systems remain operational sources, while Core remains lifecycle authority.
- **Studio projection**: the [AI-SDLC projection v1](integrations/studio-projection.md) composes versioned Core read DTOs with flavor-owned policy projections behind a Core application-service boundary. Browser requests use server-issued selection ids, never filesystem paths; presentation hints are explicitly non-authoritative.

## Allowed dependencies

Agora Core (`agora-framework`, compatible range) and development-only test/lint tooling. No LLM SDK, cloud SDK or provider runtime dependency.

## Pending decisions

- Final compatible Agora Core range (depends on a released Core boundary).


## Agent capability manifests

`agora-ai-sdlc/agent-capability-manifest/v1` declares, per agent runtime, which integration mechanisms it supports (`aisdlc runtimes --capabilities`). It is static: no lifecycle state, Laya decisions, approvals, availability or observations. Discovery observes installation, policy decides use, Laya advises, Core is authority. Every capability id is explicit; unknown agents or ids fail closed.

Adding an adapter: register a manifest in `agent_capabilities.py` via `build_manifest` with every id claimed explicitly (claim only what the adapter implements), then add it to the parity test.

## Execution requirements

`agora-ai-sdlc/execution-requirements/v1` (`execution_requirements.py`) turns a deterministic execution bundle plus *accepted* advisory (Laya) answers into provider-neutral requirements: activity class, reasoning tier (`local|standard|frontier|human`), risk, security review, validation focus and required capability ids. The action-to-capability mapping is owned by AI-SDLC. Advisory answers can only raise tier, risk or security focus; low-confidence, invalid or failed answers are kept as escalations and never remove a deterministic requirement. `human` yields a non-executable human-authority requirement. Advisory model/checkpoint is provenance only; no runtime or provider is named.

## Capability admission

`select_runtime(..., requirements=, availability=)` evaluates each candidate in configured order: policy, budget, availability, agent capabilities, model binding; the first admissible candidate wins, with no scoring or LLM call. Blocker codes: `runtime.agent_required` (model runtime alone, e.g. Ollama), `runtime.agent_unknown`, `runtime.capability_missing` (with `missing_capabilities` per considered candidate), `runtime.model_binding_missing` (local tier without a model binding), `runtime.integration_unavailable`, `runtime.model_unavailable`, `runtime.human_authority_required` (terminal). Static manifests are never mixed with discovery observations. Fallback after an admission failure needs the explicit signals `runtime-unavailable` or the opt-in `capability-mismatch`; ordinary task failure still cannot change runtime.

## Execution envelope

`agora-ai-sdlc/execution-envelope/v1` (`execution_envelope.py`) carries the exact next authorized operation: work identity and Core state revision, responsible actor and role, `ExecutionRequirements`, the runtime binding (agent + model) and a structured `next_transition` (stable operation id plus ordered typed arguments; the `display` string is derived). Actor, role, agent and model are separate fields; the actor is always explicit and validated against Core, so a runtime name (`claude`) never resolves to an actor (`ai-claude`). A human boundary yields a non-executable `stop.human_authority` envelope. Adapters call `verify_integrity` (digest check rejects any altered operation or argument) and `validate_current` before mutation; stale revision, a new human boundary, revoked authority or an inadmissible binding return typed reasons and require recalculation.

## Runtime adapter SPI

`runtime_adapter.py` defines the seam between an `ExecutionEnvelope` and a native agent runtime. `RuntimeAdapter` exposes `capability_manifest`, `health`, `plan_projection`, `prepare_execution`, `launch` and `describe`; providers only implement `health`, `plan_projection` and `render_invocation`. `AdapterRegistry` is keyed by canonical agent id, fails closed on unknown, missing or duplicate adapters, and rejects any adapter whose advertised capabilities differ from the canonical manifest. `prepare_execution` verifies envelope integrity and rejects stop envelopes, other agents' envelopes and any adapter that alters the operation, arguments or digest. Managed projection (`sync_projection`) writes only marked text blocks or named JSON keys, preserves unmanaged content, backs up before replacing, is idempotent, refuses paths outside the workspace, secret-looking content and unparseable files, and supports dry-run. Diagnostics are sanitized. A concrete adapter must pass `tests/support/adapter_conformance.py` and needs no change to lifecycle code.

## Claude Code adapter

`claude_code_adapter.py` implements the SPI for Claude Code (`claude` / `claude-code`). Flags used were checked against Claude Code 2.1.281 (`--print`, `--output-format json`, `--model`, `--permission-mode`, `--allowedTools`, `--no-session-persistence`); versions below 2.1.0 are reported unsupported by `health()` before launch. Native surfaces: `CLAUDE.md` guidance (managed block) and non-interactive execution with the envelope on stdin. Skills, MCP, subagents and a reviewer boundary are not projected yet and appear as `unsupported_surfaces`. Model assignment: an explicit Anthropic model id becomes `--model`; `configured-default`/none uses the native default; another provider or an unsafe id fails with a typed error, and no model name is ever invented. Output is parsed as `{result, is_error}`; malformed output fails typed, and prose never counts as approval or completion: AI-SDLC reconciles against Core. An optional live check runs with `AISDLC_LIVE_CLAUDE=1`.

## Codex adapter

`codex_adapter.py` implements the SPI for Codex (`codex`). Flags were checked against codex-cli 0.156.1 (`exec`, prompt on stdin via `-`, `--ephemeral`, `--color never`, `--sandbox`, `--model`); versions below 0.156.0 are reported unsupported by `health()`. Native surfaces: `AGENTS.md` guidance (managed block) and non-interactive `codex exec`; the sandbox is `workspace-write` only when the envelope requires `workspace.write`, otherwise `read-only`, never `danger-full-access`. Skills, MCP, subagents and reviewer isolation are not projected and appear as `unsupported_surfaces`. Only the OpenAI provider is supported: an explicit model id becomes `--model`, `configured-default`/none uses the native default, and another provider or an unsafe id fails with a typed error. Output is raw text (JSONL parsing is not claimed): empty output fails typed, and prose never approves or transitions anything. Optional live check: `AISDLC_LIVE_CODEX=1`. The adapter never selects another runtime as fallback.

## OpenCode + Ollama

`opencode_adapter.py` implements the SPI for OpenCode (`opencode`), the reference proof that an agent runtime and a model runtime compose. Flags were checked against OpenCode 1.18.32 (`run`, `-m provider/model`); execution goes through the existing fail-fast supervisor (`opencode_runner`), which injects the Ollama provider through per-invocation inline config, so no provider configuration is persisted and unrelated providers, tools and aliases are untouched. Native surface projected: `AGENTS.md` guidance (managed block); skills, MCP, subagents and reviewer isolation are reported as unsupported surfaces. An explicit `provider/model` binding is mandatory (`adapter.model_required`); the adapter never lets the supervisor auto-select a model and never pulls one.

Discovery reports Ollama as a model runtime (`kind: model`) with its local model ids (`ollama list`), and admission rejects a binding when the service is down or the requested model is absent (`runtime.model_unavailable`, reason `model-not-present`); a tagless request matches `<name>:latest`. Ollama alone is rejected with `runtime.agent_required`. A route candidate that is a binding is identified as `agent+provider/model`, so the same agent may appear with several explicit models; a different provider is only considered when it is an explicit candidate.

## Execution candidate

`agora-ai-sdlc/execution-candidate/v1` (`execution_candidate.py`) freezes the exact subject a reviewer or verifier inspects: repository, swarm/work, Work revision, kind (`commit`, `base-diff`, `artifact-set`, `worktree-snapshot`), full target/base commits, changed-path manifest and artifact `(uri, sha256)` pairs, hashed canonically into a `subject_hash` (no prompts are hashed). Commit candidates resolve refs to full commit ids and exclude live worktree edits. `worktree-snapshot` is the explicit bounded exception for uncommitted review (at most 500 files of 1 MB): it is marked not immutable with its limitations and is rejected where an immutable subject is required. `check_current` reports why an old candidate no longer applies (commit, artifact, revision or path change); a model's claim to have reviewed the latest code is never proof. The candidate reference travels inside the `ExecutionEnvelope` (covered by its digest), and `bind_envelope` rejects substitution. `review_evidence_input` maps a result that carries the subject hash to ordinary Core `AddEvidenceInput` (`tested_commit`, artifact refs, `dedupe_key` = subject hash; `session_id` only when the installed Core supports it). No second review authority or approval record exists: Core and method policy decide what the evidence means.
