# Budgets And Governed Fallbacks

Issue #25 defines explainable runtime selection before launch. Routes are explicit ordered preferences by activity class; the policy does not score, benchmark or infer a preferred provider. Typical activity classes are planning, implementation, review, security review and operations, but projects may define their own stable names.

Each candidate carries projected usage plus the already evaluated data-classification and independent-review decisions. A candidate is eligible only when both policies allow it and every configured work or swarm budget can prove sufficient remaining capacity. For any limited dimension, missing consumed or projected usage is unknown and never zero.

## Fallback

Fallback order is configuration, not an optimization. Agora Core recognizes executable availability and quota/rate-limit results. This policy accepts the resulting structured signal (`quota` or `runtime-unavailable`); it never parses provider logs. Budget checks may produce `budget-exhausted` or `budget-unavailable`. A route must explicitly authorize the applicable signal before the next configured candidate can be selected.

Ordinary task failures, timeouts, output limits and non-quota nonzero exits never change provider. They return a blocker and require intervention or a fresh authorized decision. Every fallback candidate is rechecked against data, review and budget policy.

## Measurement basis

Usage and cost amounts are not equally trustworthy, so every consumed dimension carries the basis Agora Core recorded for it: `measured`, `provider-reported` or `unknown`. `budget_from_core` copies Core's `consumed_measurement` (Agora Core 0.9.1 or later), which is the weakest basis among the records that contributed to a dimension. Anything the summary does not state is `unknown`: an older Core without the field, a dimension it omits, and a work item with no usage records all report `unknown`, and an empty ledger is never presented as a measured zero. The decision output repeats the basis per scope and dimension in `consumed_measurement` next to `consumed_budget`.

The basis is evidence metadata. Budget sufficiency, fallback signals and eligibility are computed exactly as before and never change with the basis; a caller that needs measured-only accounting must enforce that on the reported basis.

## Core Authority

Core `UsageSummary` is the durable source for work consumption and limits. `budget_from_core` maps it without creating a ledger. Swarm-level limits are supplied as an additional governed budget scope. Changes to delegated budgets use Core `agora/budget-amendment/v1`; this policy does not amend budgets itself.

The decision output records the activity class, selected runtime, configuration-derived reason, fallback reason, candidates considered and consumed budget by scope. Callers persist that output as evidence and use the selected runtime through Core session APIs. Model provenance records the resulting selection or fallback metadata when Core can supply it. Durable Core session fields for the actual fallback and reason remain tracked in [Agora Core #54](https://github.com/Modern-Ash/agora/issues/54); this policy does not create a substitute session store.

The deterministic reference implementation is `agora_ai_sdlc.runtime_selection`.
