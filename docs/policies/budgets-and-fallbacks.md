# Budgets And Governed Fallbacks

Issue #25 defines explainable runtime selection before launch. Routes are explicit ordered preferences by activity class; the policy does not score, benchmark or infer a preferred provider. Typical activity classes are planning, implementation, review, security review and operations, but projects may define their own stable names.

Each candidate carries projected usage plus the already evaluated data-classification and independent-review decisions. A candidate is eligible only when both policies allow it and every configured work or swarm budget can prove sufficient remaining capacity. For any limited dimension, missing consumed or projected usage is unknown and never zero.

## Fallback

Fallback order is configuration, not an optimization. Agora Core recognizes executable availability and quota/rate-limit results. This policy accepts the resulting structured signal (`quota` or `runtime-unavailable`); it never parses provider logs. Budget checks may produce `budget-exhausted` or `budget-unavailable`. A route must explicitly authorize the applicable signal before the next configured candidate can be selected.

Ordinary task failures, timeouts, output limits and non-quota nonzero exits never change provider. They return a blocker and require intervention or a fresh authorized decision. Every fallback candidate is rechecked against data, review and budget policy.

## Core Authority

Core `UsageSummary` is the durable source for work consumption and limits. `budget_from_core` maps it without creating a ledger. Swarm-level limits are supplied as an additional governed budget scope. Changes to delegated budgets use Core `agora/budget-amendment/v1`; this policy does not amend budgets itself.

The decision output records the activity class, selected runtime, configuration-derived reason, fallback reason, candidates considered and consumed budget by scope. Callers persist that output as evidence and use the selected runtime through Core session APIs. Model provenance records the resulting selection or fallback metadata when Core can supply it. Durable Core session fields for the actual fallback and reason remain tracked in [Agora Core #54](https://github.com/Modern-Ash/agora/issues/54); this policy does not create a substitute session store.

The deterministic reference implementation is `agora_ai_sdlc.runtime_selection`.
