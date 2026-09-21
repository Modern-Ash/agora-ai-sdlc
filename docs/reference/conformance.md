# Compatibility conformance

The conformance engine evaluates a versioned compatibility profile against local project/repository capability facts. It is deliberately generic: the engine does not contain cloud-, model-, provider- or vendor-specific scoring rules.

## Command

```bash
agora-ai-sdlc conformance aws-original
agora-ai-sdlc conformance lg-enterprise
```

By default the command looks for:

```text
.agora/ai-sdlc/conformance-facts.yaml
```

under the selected project root. Use `--facts PATH` to supply an explicit facts file and `--root PATH` to change the default project root.

Output modes:

```bash
agora-ai-sdlc conformance aws-original
agora-ai-sdlc conformance aws-original --json
agora-ai-sdlc conformance aws-original --strict
```

A valid report returns exit code 0 by default even when it contains `FAIL`; this lets humans inspect incomplete projects without treating the command itself as an input error. `--strict` returns 1 when any capability result is `FAIL`. Invalid profiles, facts or explicit input paths return 2.

## Facts contract

Facts use `agora-ai-sdlc/conformance-facts/v1`:

```yaml
schema: agora-ai-sdlc/conformance-facts/v1
facts:
  - capability: human-validation
    status: PASS
    evidence:
      - repo://docs/reviews/approval.md
    reason: Accountable approval is recorded.
  - capability: level-1-plan
    status: PARTIAL
    evidence:
      - repo://plans/plan.md
    reason: A plan exists but recursive decomposition is not yet evidenced.
    remediation: Add traced child plans and approval evidence.
```

Allowed statuses are:

- `PASS`
- `PARTIAL`
- `FAIL`
- `NOT_APPLICABLE`

Facts are local declarations/evidence inputs. Later rule-provider work can derive the same facts from repository structures and Core facts, but the engine contract remains unchanged.

## Evaluation semantics

The selected compatibility profile declares capabilities as `required`, `optional` or `unsupported`.

| Profile declaration | No fact | Explicit fact |
| --- | --- | --- |
| required | FAIL | fact status |
| optional | NOT_APPLICABLE | fact status |
| unsupported | NOT_APPLICABLE | NOT_APPLICABLE presentation; supplied evidence is retained |

Facts for capabilities not declared by the selected profile are rejected. This catches misspellings and prevents unrelated evidence from silently affecting a report.

Required capabilities fail closed when evidence is absent. Missing optional capabilities are not treated as failures.

Overall status is deterministic:

1. any `FAIL` -> `FAIL`;
2. otherwise any `PARTIAL` -> `PARTIAL`;
3. otherwise any `PASS` -> `PASS`;
4. otherwise -> `NOT_APPLICABLE`.

## Result contract

JSON output uses `agora-ai-sdlc/conformance-result/v1`. Each capability result contains:

- capability id;
- profile requirement class;
- status;
- evidence references;
- reason;
- source compatibility contract version;
- remediation when the result is incomplete or failing.

Checked-in schemas:

- [conformance-facts-v1.schema.json](../../contracts/conformance/conformance-facts-v1.schema.json)
- [conformance-result-v1.schema.json](../../contracts/conformance/conformance-result-v1.schema.json)

The output is intended for CI, dashboards and later evidence-backed Marketplace documentation.

## Offline and neutrality guarantees

Evaluation reads only packaged compatibility profiles and local files. It performs no network discovery, no provider API calls and no credential lookup. The engine does not know how AWS-original or LG-enterprise capabilities are implemented; methodology-specific fact derivation is layered on top of this generic contract.
