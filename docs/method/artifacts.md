# AI-SDLC artifacts and traceability

Templates live in [templates/](../../templates/) and are shipped in the wheel. Validation is implemented in `agora_ai_sdlc.artifacts` (pure functions, no network). Templates contain no provider-specific prompt syntax; every field is documented here so any actor, human or model, can fill them.

## Front matter (schema `agora-ai-sdlc/artifact/v1`)

| Field | Meaning |
|---|---|
| `schema` | Must be `agora-ai-sdlc/artifact/v1` |
| `kind` | One of the kinds below; matches the Agora artifact kind registered on the work item |
| `version` | Template schema version, currently `1` |
| `id` | Traceability id `PREFIX-NNN` (empty in templates; required in filled artifacts) |
| `work`, `revision` | Work item id and the work revision the artifact belongs to |
| `traces-to` | Ids of parent artifacts (see chain) |
| `criteria` | (requirements) acceptance-criterion ids defined by this document |
| `covers-criteria` | (test-strategy) criterion ids the strategy covers |
| `required-sections` | `##` headings that must exist in a filled artifact |

## Kinds, prefixes and allowed parents

| Kind | Prefix | Traces to | Template |
|---|---|---|---|
| readiness-assessment | RDY | root | readiness-assessment.md |
| intent | INT | root | product-intent.md |
| clarification | CLR | any | clarification.md |
| unit-of-work | UOW | intent | unit-of-work.md |
| requirements | REQ | unit-of-work | requirements.md |
| domain-model | DOM | requirements | domain-model.md |
| architecture | ARC | requirements | architecture.md |
| threat-model | THR | architecture | threat-model.md |
| test-strategy | TST | requirements | test-strategy.md |
| implementation-plan | IMP | architecture, test-strategy | implementation-plan.md |
| deployment-plan | DEP | implementation-plan | deployment-plan.md |
| rollback-procedure | RBK | deployment-plan | rollback-procedure.md |
| operational-readiness | OPR | deployment-plan | operational-readiness.md |
| learning-record | LRN | any | learning-record.md |
| rework-record | RWK | any | rework-record.md |

Chain: intent -> unit of work -> requirements (criteria) -> architecture / test strategy (coverage) -> implementation plan (code and test references) -> deployment plan.

## Deterministic checks

`check_traceability` fails with stable codes: `trace.duplicate_id`, `trace.missing_parent`, `trace.dangling`, `trace.parent_kind`, `trace.uncovered_criterion`, `trace.unknown_criterion`. Artifact parsing fails with `artifact.front_matter`, `artifact.schema`, `artifact.kind`, `artifact.version`, `artifact.missing_section`, `artifact.id`, `artifact.trace_format`, `artifact.criterion`.

## Notes

- Every artifact kind required by a gate has a template (tested). `build-verified` now requires `implementation-plan` (previously `implementation`): the plan is updated with code and test references as work is delivered.
- Core gates only check that an artifact of a kind is registered; these validators are separate, local checks. They are not yet wired into a gate or into `verify_all.py`.
- Code/test evidence and deployment linkage are expressed through the implementation-plan and deployment-plan references; evidence records themselves stay in Core.
