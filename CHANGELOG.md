# Changelog

## Unreleased

## 0.3.0 - 2026-09-27

- Add provider-neutral cost-aware routing with ordered economic tiers: `local -> free -> paid-efficient -> paid-standard -> frontier`.
- Prefer OpenCode + local/free model execution and keep paid providers behind explicit policy, availability, capability and budget admission.
- Add bounded local/free retries before escalation, per-tier call budgets, Core Work-budget enforcement and economic telemetry through `aisdlc economics`.
- Add bounded escalation packages and a read-only paid planner path that returns non-authoritative repair advice to the original cheap executor instead of taking over repository execution.
- Record provider-reported planner usage in Agora Core when supported and fail closed on additional paid routing when paid usage cannot be accounted.
- Add `purpose=executor|planner|reviewer` runtime candidates so expensive planning/review can be separated from high-volume implementation.
- Add the paid Skill Planner: Codex/Claude may interpret bounded Skills at `paid-efficient`/standard tiers, while OpenCode/Ollama or other cheap executors perform implementation/test/repair loops.
- Cache Skill Planner output by input digest so retries reuse paid planning work instead of repeating model calls.
- Make `aisdlc start` honor `cheap-first` routing when no explicit runtime/model override is provided.
- Extend the installer to validate and persist cheap-first routing configuration, retry limits, call budgets and runtime purposes.
- Keep Laya advisory and provider-neutral: it classifies reasoning demand and context relevance but never selects or authorizes a provider.


## 0.2.0 - 2026-09-26

- Publish a single-tool installation surface that exposes `agora`, `aisdlc` and `agora-ai-sdlc` from the Agora AI-SDLC distribution while resolving Agora Core as a normal dependency.
- Wire the provider-neutral runtime layer into the real Inception, Guided and Construction execution paths through `ExecutionRequirements -> RuntimeBinding -> ExecutionEnvelope -> RuntimeAdapter`.
- Fail closed when an executor run leaves Agora governed state invalid (new `governance_guard`), and warn in `aisdlc doctor` when Prettier may rewrite `.agora/`.
- Add the provider-neutral runtime layer (epic #252): `runtime-binding/v2` agent/model taxonomy, canonical agent capability manifests, `ExecutionRequirements`, deterministic capability admission, `ExecutionEnvelope`, the `RuntimeAdapter` SPI with Claude Code, Codex and OpenCode(+Ollama) adapters, immutable `ExecutionCandidate` review subjects, a shared conformance suite, `aisdlc runtimes --capabilities|--migrate-preview|--diagnose` and the "Adding a new agent runtime" guide. Compatibility: v1 flat runtime entries stay readable and JSON consumers keep their fields (`kind`, `models` and `binding` are additive); `default_registry` takes a project root; the opt-in fallback signal `capability-mismatch` is new.
- Stabilize the continuous Flow branch against current main and preserve Expert CLI Construction execution alongside Automagic Flow.
- Evolve Agora Flow into a continuous AI-DLC wizard with phase/substep progress, Level 1 Plan preview, transparent Decision Cards, transversal human validation checkpoints and first-class AI-DLC artifacts.
- Add the continuous Agora Flow AI-DLC wizard with inline clarification, AI-DLC phase/substep guidance, transparent method outputs, Enter-to-confirm governed execution, and seamless Start -> wizard flow.
- Enrich Method Pack 0.2.0 with first-class AI-DLC Inception outputs (Level 1 Plan, User Stories, NFR, Risk Register, Measurement Criteria, Units and Bolts) and Construction outputs (Domain Design, Logical Design and Deployment Unit), while retaining 0.1.0 unchanged for compatibility.
- Add the optional local Laya Decision Plane, Progressive Intelligence and visible Context Economy: confidence-gated routing, fail-open semantic pruning, before/after context estimates and persisted lean execution context.
- Runtime selection now carries Agora Core's usage measurement basis (measured, provider-reported, unknown) per consumed dimension; missing values are unknown, never measured.
- Add the AI-SDLC Studio projection provider (`agora_ai_sdlc.studio_projection`) for Agora Core >=0.9, mapping the flavor manifest and Core session provenance and reporting unsupported sections as explicit unavailable.
- Add the Regulated Delivery Readiness package and a statement of work template to the professional-services documentation.
- Declare compatibility with Agora Core `>=0.8.2,<0.10` (verified on 0.8.2 and 0.9.0) and publish the versioning, compatibility and release policy.
- Document prerequisites, permissions and failure modes for the security-findings, generic CI evidence and operational-evidence profiles.
- Publish the cross-repository AI-SDLC Studio projection v1 contract, fixtures, ownership map, and compatibility table.
- Add the Regulated profile with Core-signed critical actions, segregation controls, observed provenance, and immutable exception and retention metadata.
- Add the Modernization profile with explicit legacy unknowns, incremental slice traceability, equivalence and cutover gates.
- Add the Enterprise profile with signed project registries, inherited policy validation, provenance, and previewable upgrades.
- Add the preview-first Starter profile and deterministic one-team repository bootstrap.
- Add provider-neutral operational metrics, release readiness, and governed Core control-band proposals.
- Add read-only-by-default GitLab delivery and Jira work-management follow-on profiles.
- Add provider-neutral security findings, depth thresholds, and accountable decisions.
- Add the provider-neutral CI/CD evidence profile and multi-provider sample.
- Add the offline-first GitHub delivery integration profile.
- Package skeleton.
