# Agora Flow continuous AI-DLC wizard

Agora Flow is the interaction layer for practicing AI-DLC without requiring users to memorize the
method, author methodology prompts, or manually orchestrate agents.

The wizard is intentionally **simple by default and transparent on demand**. It abstracts operational
complexity but never hides facts, evidence, decisions, model/runtime selection or human authority.

## Entry points

For new work:

```bash
aisdlc start --issue 26
```

On an interactive terminal, Start bootstraps the governed Work and continues directly into the wizard.

For existing work:

```bash
aisdlc continue
```

The user remains in the same session while Agora re-reads Core after each confirmed action.

## Two-level progress

The first level is the canonical AI-DLC lifecycle:

```text
Inception -> Construction -> Operations
```

The second level is dynamic method guidance inside the phase.

### Inception

```text
Understand -> Clarify -> Level 1 Plan -> Stories -> NFR/Risk -> Units -> Bolts
```

### Construction

```text
Semantic Elevation (brownfield when needed)
    -> Domain Design
    -> Logical Design
    -> Implementation
    -> Testing
    -> Deployment Unit
```

### Operations

```text
Deployment -> Observability -> Feedback
```

The sequence shown by the wizard is an explanation of the current Work, not a hard-wired pathway
state machine. Core lifecycle semantics remain the three phases; adaptive plans determine the actual
work to execute.

## Every screen answers the same questions

A normal wizard view should make these facts obvious:

1. **Where am I?** Current AI-DLC phase and substep.
2. **What does Agora know?** Intent, Work, Core state, target, gate and responsible role.
3. **What is missing?** Material gaps, artifacts, criteria, evidence or policy blockers.
4. **What exists?** Observed AI-DLC outputs and evidence.
5. **What does Agora propose?** One next action, not a menu of methodology commands.
6. **What will happen if I confirm?** Context assembly, executor, bounded action and Core re-inspection.
7. **Why this choice?** Decision source, confidence and method guidance.
8. **What is the human boundary?** Approval/authority that automation cannot cross.

## Interaction model

The stable happy-path controls are:

```text
[Enter] Confirm
[A] Adjust
[D] Details
[X] Exit
```

- **Confirm** executes the proposed safe step.
- **Adjust** changes the executor/model or returns to the decision surface.
- **Details** expands raw Core blockers, structured state, evidence, commands and provenance.
- **Exit** stops without fabricating progress.

Material ambiguity interrupts the action controls with one bounded question. The answer is persisted as
explicit Work context and is not asked again.

## Clarification without prompts

Semantic gaps discovered during Inception are converted into direct human questions:

```text
Hace falta una aclaración antes de continuar

¿Debe el retry conservar el Idempotency-Key original?

Por qué pregunta Agora:
La respuesta cambia el contrato que guiará diseño, implementación y tests.

Respuesta:
```

Answers are persisted under:

```text
.agora/ai-sdlc/wizard/<work>/ANSWERS.json
```

They are supplied to later governed executor sessions as explicit human-provided context.

## Method outputs, not hidden files

The main view names the AI-DLC artifacts in method language:

```text
AI-DLC method outputs
  ✓ Intent
  ✓ Level 1 Plan
  ! User Stories
  · NFRs
  · Risk Register
  · Measurement Criteria
  · Units
  · Suggested Bolts
```

Only an observed artifact is marked complete. A gate not requiring an artifact does not make it appear
completed.

## Agora Flow intelligence card

Before execution, the wizard exposes how the recommendation was made:

```text
Agora Flow intelligence
  • Decision source: Laya (local System-1)
  • tier=local · confidence=0.96
  • Context: 18 candidate files -> 6 selected
  • Estimated context: ~8,410 -> ~2,730 tokens · ~5,680 avoided
  • 1 uncertain file retained by fail-open safety
```

If Laya is unavailable, the wizard says the decision came from deterministic/Core behavior and
continues without blocking delivery.

## Decision Card before every action

The wizard does not ask for a blind confirmation. Before a material action it renders one compact
Decision Card containing:

- **why** Agora proposes the action;
- **what will run** if the user confirms;
- **what cannot happen automatically**;
- selected executor/runtime when applicable;
- decision source and confidence;
- candidate versus selected context and estimated token economy;
- security/reasoning escalation warnings;
- the exact human/Core checkpoint to which control returns.

Example:

```text
╭─ Proposed decision
│ Prepare the remaining Construction outputs.
│
│ Why
│   • Deployment Unit is still missing.
│   • AC-002 still needs verification.
│   • Local System-1 classified this as local with confidence 0.96.
│
│ If confirmed, Agora will
│   1. Assemble bounded context.
│   2. Run one governed preparation iteration.
│   3. Persist artifacts/evidence.
│   4. Re-read Core and recalculate.
│
│ Executor: Ollama · qwen3:8b [local]
│ Intelligence: Laya local System-1 → local
│ Context: 12 candidate files → 5 selected; ~8400 → ~2900 tokens
│
│ Boundaries
│   • no implicit human approval
│   • no gate bypass
│   • no implicit merge/deployment
│
│ Next checkpoint: return to the wizard for human/Core validation
╰────────────────────────────────────────────────────────────────────────
```

This is the primary Agora Flow usability contract: abstraction of operational complexity without
abstraction of evidence, rationale or authority.

## Level 1 Plan and recursive validation

Whenever the current Inception draft contains a Level 1 Plan, the wizard previews its current top-level
steps instead of hiding the plan inside a Markdown artifact. The full artifact remains available through
Details.

Validation is transversal rather than a final Review phase. Every method substep exposes the next
human validation checkpoint before the next semantic enrichment or lifecycle transition. This models
AI-DLC's human oversight as an early-error-correction/loss-function behavior rather than a final signoff.

## Progressive Intelligence

Agora uses the cheapest sufficient layer rather than sending every decision to a generative model:

```text
Core/deterministic
       ↓
Laya System-1
       ↓
local/free generative executor
       ↓
external/frontier executor
       ↓
human authority
```

This affects execution efficiency, not AI-DLC lifecycle meaning.

## Context Economy

The Context Graph and Execution Bundle determine the candidate context first. Laya may prune only those
candidates. It cannot introduce unrelated files.

Safety rules:

- changed and dirty files are always retained;
- low-confidence classifications are retained;
- original documents are selected rather than summarized;
- the before/after token estimate is shown to the user;
- the selected context is persisted as `LEAN_EXECUTION_CONTEXT.json` and used by the executor.

The principle is **select, don't summarize**.

## Brownfield experience

When the Work is brownfield, the wizard calls out the semantic-elevation requirement explicitly:

```text
Construction · 1/6
▶ Semantic Elevation

Brownfield semantic elevation
  • build/review static system model
  • build/review dynamic system model
  • only then proceed to Domain Design
```

This keeps context concise and accurate before modifying existing code.

## Human checkpoints

Review is not a final phase. Validation happens throughout the lifecycle.

The wizard stops at meaningful human decisions such as:

- unresolved business ambiguity;
- Level 1 Plan validation;
- Unit/Bolt decomposition decisions;
- material domain or architecture trade-offs;
- risk acceptance;
- deployment configuration;
- final outcome/production authority.

It does not stop for mechanical confirmations such as reading a file or running an already-authorized
deterministic check.

## Adoption goal

A practitioner familiar with software delivery should be able to learn AI-DLC while using Agora Flow.
Method vocabulary is preserved, but every current term is explained inline the first time it matters.

This turns the method from a prompt/documentation exercise into an executable, observable delivery
experience.
