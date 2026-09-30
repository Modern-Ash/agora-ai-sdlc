# Decision Plane Coverage v1

This document freezes the first measurable coverage map for the Agora AI-SDLC Decision Plane before Agorix baseline/dogfood work resumes.

## Authority model

```text
Core facts
  -> System-0 deterministic resolution
  -> Laya System-1 advisory classification
  -> provider-neutral ExecutionRequirements
  -> deterministic economic/capability routing
  -> generative executor only when required
  -> human authority at explicit gates
```

System-0 and Laya are advisory inputs to execution planning. Neither may approve gates, mutate lifecycle authority, select a provider by name, or manufacture evidence.

## Coverage matrix

| Decision | System-0 | Laya | Confidence / abstention | Cache / batch | Downstream use | Metrics | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `reasoning_tier` | yes: human/security floors where explicit | yes | per-question threshold; low confidence escalates | FlowDecisionSession cache; joint execution questions | ExecutionRequirements -> ExecutionPolicy | advisory + economics | covered |
| `planner_needed` | yes: human => none | yes | per-question threshold | joint Laya execution batch when supported | planner economic ceiling | advisory + economics | covered |
| `change_risk` | yes: explicit security floor | yes | per-question threshold | joint execution batch | requirements risk; validation/routing constraints | advisory + economics | covered |
| `security_review` | yes: explicit security markers | yes | stricter threshold | joint execution batch | requirements + security validation focus | advisory + economics | covered |
| `validation_focus` | yes for explicit security/operations facts | yes | per-question threshold | joint execution batch | validation focus | advisory + economics | covered |
| context relevance | deterministic Context Graph defines candidates | yes: required/useful/irrelevant | low confidence fails open and keeps context | batched `decide_many` + content/provider/question cache | semantic pruning before final token budget | context metrics | covered |
| `llm_needed` | not explicit | not explicit | none | none | currently inferred indirectly from workflow/action paths | only observed generative calls | GAP |
| `reviewer_needed` | policy can require independent review, but no typed decision | not explicit | none | none | `isolated_reviewer` capability can be required by caller | review evidence exists elsewhere | GAP |
| `context_needed` | Context Graph always starts from deterministic candidates | relevance is per artifact, not a top-level need decision | relevance thresholds | relevance cache/batch | no top-level skip/empty-context contract | context metrics | PARTIAL |

## Existing implementation

- `system0_decisions.py`: deterministic advisory floors and per-question thresholds.
- `execution_decisions.py`: typed execution questions and confidence evaluation.
- `laya_provider.py`: local System-1 provider with heterogeneous batch support.
- `flow_decision_session.py`: Work-snapshot cache for advisory evaluation, requirements and policy.
- `execution_requirements.py`: provider-neutral accepted-signal projection.
- `execution_policy.py`: deterministic cheap-first economic ceiling.
- `context_relevance.py` / `context_selection.py`: batched, cache-aware, fail-open semantic pruning.
- `execution_economics.py`: observed execution/advisory/token telemetry without invented counterfactual savings.

## Gaps to implement before benchmark

### G1 — Explicit generative-need decision

Add a provider-neutral `llm_needed` decision whose purpose is to avoid generative execution when the next bounded action is already satisfiable by deterministic machinery/templates.

Required properties:

- System-0 resolves `no` for known deterministic actions.
- Laya may classify unresolved bounded actions.
- low confidence must fail open to the existing generative path;
- `llm_needed=no` cannot bypass required artifacts/evidence/gates;
- record an avoided generative call only when the workflow actually suppresses an otherwise eligible generative invocation.

### G2 — Review need as a typed requirement

Separate three facts:

1. deterministic policy requires independent review;
2. advisory classification suggests focused generative review;
3. human authority/review is mandatory.

Laya may help classify review need/focus, but may never satisfy review evidence or choose the reviewer/provider.

### G3 — Top-level context need

Before per-artifact relevance classification, decide whether the next generative action needs repository artifact context at all.

- System-0 should resolve obvious no-context actions.
- Laya may classify unresolved context need.
- low confidence fails open to deterministic Context Graph candidates.
- per-artifact relevance remains the second-stage pruning mechanism.

## Measurement contract

The benchmark must distinguish observed facts from counterfactual claims.

Observed:

- System-0 resolutions;
- Laya calls, accepted/escalated answers, confidence and latency;
- cache hits;
- generative calls;
- provider-reported tokens;
- context candidate/selected tokens;
- runtime/model/tier;
- retries/escalations/outcome.

Counterfactual savings (`llm_calls_avoided`, token/cost savings) require A/B or replay evidence. An accepted Laya answer alone is not proof of savings.

## Benchmark gate

Do not tune Laya thresholds from one issue. After G1-G3 are implemented, use:

1. Agorix #80-#84 as the predominantly deterministic control workload;
2. Agorix #86-#90 as the AI-native workload;
3. replay/A-B where the same bounded decisions can be evaluated with Decision Plane enabled/disabled;
4. calibrate thresholds only after collecting representative outcomes.

## Out of scope for v1

- provider/model selection by Laya;
- lifecycle/gate authority;
- automatic approval;
- Laya fine-tuning before benchmark evidence;
- Agorix product-side Learning Decision Plane (separate architecture path after AI-SDLC benchmark foundation).
