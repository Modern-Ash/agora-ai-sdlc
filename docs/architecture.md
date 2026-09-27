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

## Cost-aware execution policy and runtime pools

Executor routing is deliberately separate from Laya classification and Core authority. `execution_policy.py`
maps provider-neutral reasoning demand to an economic ceiling using the ordered tiers
`local -> free -> paid-efficient -> paid-standard -> frontier`. Execution always starts from the
cheapest configured tier that satisfies policy, availability, capabilities and budget. A stronger tier
is considered only when cheaper candidates are inadmissible.

Projects opt in with `routing.profile: cheap-first` in `ai-sdlc/project.yaml`. Paid automatic routing
requires `allow_paid_auto: true`; frontier additionally requires `allow_frontier_auto: true`. This
makes the expensive path fail closed by default while still allowing explicit runtime/model overrides.

Example:

```yaml
routing:
  profile: cheap-first
  allow_paid_auto: true
  allow_frontier_auto: false
  candidates:
    - tier: local
      agent: opencode
      model: ollama/qwen3-coder:latest
    - tier: free
      agent: opencode
      model: opencode/free-coder
    - tier: paid-efficient
      agent: codex
      model: openai/configured-efficient
    - tier: paid-efficient
      agent: claude
      model: anthropic/configured-efficient
    - tier: paid-standard
      agent: codex
      model: openai/configured-standard
    - tier: frontier
      agent: codex
      model: openai/configured-frontier
```

Model names are project configuration, never lifecycle semantics. Teams can bind each provider's
`paid-efficient`, `paid-standard` and `frontier` entries to whichever concrete models or reasoning
profiles are appropriate without changing Agora. An explicit `--agent`/model choice remains an override.

## Skill planner and cheap executor separation

A cost-aware workflow can use paid reasoning without turning the paid runtime into the implementation worker.
`skill_planner.py` evaluates the provider-neutral `ExecutionPolicy.planner_tier` and, when paid automatic
routing is explicitly enabled, selects the cheapest admissible Codex/Claude planner from
`paid-efficient -> paid-standard`. The planner receives only the installed guided Skill, phase guidance
and deterministic ExecutionBundle through a read-only `planning.advise` envelope.

The resulting plan is persisted under `.agora/ai-sdlc/planning/<work>/` and handed to the selected
executor as non-authoritative guidance. Planner input is content-addressed: identical Skill + bundle input
reuses the existing plan, so local retries do not repeat the paid planning call.

This creates a deliberate split:

```text
Core + Laya
   |
   +--> Skill Planner: Codex/Claude paid-efficient first (read-only, bounded)
   |         |
   |         +--> persisted advisory plan
   |
   +--> Executor: OpenCode + local/free model first
             |
             +--> edit / build / test / repair loop
```

`aisdlc start` also honors an opt-in `cheap-first` pool when no explicit `--agent` or `--model`
override is supplied, so initial Inception execution does not silently default to a paid worker.
Explicit runtime/model choices remain overrides.

## Bounded retry, diagnostic escalation and economics

Cheap-first execution uses two additional safeguards before a stronger executor is considered:

1. `retry_limits` bounds automatic retries for `local` and `free` tiers. Ordinary failure does not
   immediately change provider.
2. After cheap retries are exhausted, AI-SDLC may build an
   `agora-ai-sdlc/escalation-package/v1` containing only the Work objective, acceptance criteria,
   relevant changed/dirty paths, verification commands, deterministic verification diagnosis, failed
   runtime identity and bounded error text.

When paid automatic routing is enabled, the package can be sent to the cheapest admissible
`paid-efficient`/ `paid-standard` **read-only advisor** through Codex or Claude. The advisor does not
become the Work executor and cannot approve or transition anything. Its advice is persisted and handed
back to the original cheap executor for one governed repair attempt.

The runtime pool also accepts `call_budgets` by economic tier. Actual adapter launches are recorded in
`.agora/ai-sdlc/economics/<work>/EVENTS.jsonl`; exhausted tier call budgets remove that tier from
automatic selection. Core token/cost budgets remain authoritative and are also passed into the existing
runtime selector when Core exposes a budget for the Work.

Example:

```yaml
routing:
  profile: cheap-first
  allow_paid_auto: true
  allow_frontier_auto: false
  retry_limits:
    local: 2
    free: 1
  call_budgets:
    paid-efficient: 6
    paid-standard: 2
    frontier: 0
```

Use `aisdlc economics --work <id>` to inspect attempts, successes, failures and escalations by tier.
The economics ledger is explanatory telemetry only; lifecycle authority and authoritative usage remain
in Agora Core.

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

## Governed-state guard

`governance_guard.py` wraps every executor session launch (Inception and Construction). It runs Core validation before and after the run and fails closed with `governance.regression` when the run introduced new validation errors, for example an `INTENT.md` overwritten without its front matter. Only issues the run introduced block it; pre-existing issues never do, and the guard never approves, restores or rewrites anything. `aisdlc doctor` also warns when Prettier is used without `.agora/` in `.prettierignore`, because reformatting `.agora/` breaks Core digests.
