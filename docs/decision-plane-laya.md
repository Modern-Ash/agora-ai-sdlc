# Local Decision Plane with Laya

Agora AI-SDLC uses [Laya](https://github.com/NandhaKishorM/laya) as its local System-1
decision engine. Laya is the only System-1 provider shipped by this integration and is Apache-2.0
licensed. It is deliberately separate from the generative runtimes used by Construction and Review.

## Authority boundary

The Decision Plane is advisory. It MUST NOT approve a lifecycle transition, satisfy an approval,
replace evidence, merge code or deploy software. Agora Core remains authoritative for lifecycle state,
policy, evidence and human approvals.

The escalation order is:

```text
deterministic rule -> Laya advisory decision -> generative executor -> human authority
```

Deterministic rules always win. Low-confidence Laya answers fail open and are escalated instead of
silently removing context or authorizing an action.

## Normal workflow

Laya is part of the normal AI-SDLC installation and is intentionally hidden behind the guided workflow.
Users should not need a separate Laya command for routine delivery:

```bash
pip install agora-ai-sdlc
aisdlc continue
```

`continue` uses deterministic Core state first, then Laya for cheap local classification when that can
simplify the next interaction. It presents one recommended next action, Enter accepts that default, and
a local/free executor is preselected automatically when one is already available. Paid/external
providers are never silently selected.

The default checkpoint is `typed-decisions`. Override it without changing Agora configuration:

```bash
export AGORA_LAYA_MODEL=typed-decisions
```

Laya downloads model weights on first use. After the checkpoint is present, decisions can run locally
without paid model API calls.

## Execution advice

Build the normal deterministic execution state and ask Laya for advisory routing and focused-review
signals:

```bash
aisdlc decision --root . --work issue-26
aisdlc decision --root . --work issue-26 --threshold 0.92 --json
```

The output explicitly reports `authoritative: false`. Answers below the threshold are returned in
`escalated`, which means the normal generative/human path should handle them.

The initial questions are intentionally small:

- `reasoning_tier`: local, standard, frontier or human.
- `security_review`: focused security review or normal verification.

These answers never mutate the execution bundle.

## Semantic context pruning

Agora first builds the deterministic Context Graph. Laya can only prune candidates from that graph;
it cannot introduce unrelated files or artifacts.

```bash
aisdlc context ./artifacts REQ-001 \
  --laya \
  --objective "Implement idempotent payment retry" \
  --acceptance "Retries must not duplicate charges" \
  --max-tokens 4000 \
  --json
```

For each candidate artifact Laya classifies relevance as `required`, `useful` or `irrelevant`.
A confident `irrelevant` artifact can be removed before a generative model sees it. An uncertain
classification is retained (fail open). The final token budget is enforced after semantic pruning.

This implements the principle:

```text
select, don't summarize
```

The original artifact remains the source of truth; no LLM-generated summary is inserted into the
trace chain.

## Metrics

Context selection records:

- candidate context tokens;
- selected context tokens;
- estimated tokens saved;
- Laya decision count and latency;
- confident decisions;
- escalations;
- advisory decisions that can avoid an equivalent generative classification call.

The token estimator remains provider-neutral and approximate. Savings should be treated as a benchmark
signal, not a billing claim.

## Python API

The core contract is `DecisionProvider`. The current implementation is
`LayaDecisionProvider`; keeping the contract separate prevents Laya-specific code from leaking into
the lifecycle and governance modules.

```python
from agora_ai_sdlc.laya_provider import LayaDecisionProvider
from agora_ai_sdlc.execution_decisions import advise_execution

evaluation = advise_execution(
    execution_bundle,
    provider=LayaDecisionProvider(),
    confidence_threshold=0.90,
)
```

For Context Graph pruning use `select_context_with_laya(...)`.

## Calibration and rollout

Do not assume the default checkpoint is calibrated for a repository merely because it returns a high
confidence value. Before using a Laya signal to suppress generative work at scale:

1. collect Agora decisions and their eventual human/verification outcomes;
2. measure false-confident decisions, not only aggregate accuracy;
3. tune the confidence threshold per workflow;
4. fine-tune/calibrate Laya on representative Agora decision data if needed;
5. keep high-risk and authority-bearing decisions on deterministic/human paths.

The first production target should be context relevance and execution-tier routing, where failure can
safely fall back to the existing Agora flow.
