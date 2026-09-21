# AI-SDLC artifacts and traceability

Templates live in [templates/](../../templates/) and are shipped in the wheel. Validation is implemented in `agora_ai_sdlc.artifacts` (pure functions, no network). Templates contain no provider-specific prompt syntax; every field is documented here so any actor, human or model, can fill them.

Critical artifacts declare `separation-policy` in front matter. Independent review binds to artifact kind, id, revision and digest; changing revision or content requires a new review. See [independent review policy](../policies/independent-review.md).

Readiness records identify data classifications and eligible runtimes. Launch checks calculate the effective classification from referenced inputs before invoking a runtime. See [data handling policy](../policies/data-handling.md).

## Front matter (schema `agora-ai-sdlc/artifact/v1`)

| Field | Meaning |
|---|---|
| `schema` | Must be `agora-ai-sdlc/artifact/v1` |
| `kind` | One of the kinds below; matches the Agora artifact kind registered on the work item |
| `version` | Template schema version, currently `1` |
| `id` | Traceability id `PREFIX-NNN` (empty in templates; required in filled artifacts) |
| `work`, `revision` | Work item id and the work revision the artifact belongs to |
| `traces-to` | Ids of parent artifacts (see chain) |
| `separation-policy` | Independent-review profiles required for a critical artifact revision |
| `criteria` | (requirements) acceptance-criterion ids defined by this document |
| `covers-criteria` | (test-strategy) criterion ids the strategy covers |
| `required-sections` | `##` headings that must exist in a filled artifact |

Modernization templates also use structured `behaviors`, `slice-ids`, `slice-id`, `behavior-ids`, `independently-deployable`, component/dependency lists and equivalence `comparisons`. Their normative rules are documented in the [Modernization profile](../profiles/modernization.md).

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
| legacy-inventory | LGI | root | legacy-inventory.md |
| dependency-map | DPM | legacy-inventory | dependency-map.md |
| characterization | CHR | legacy-inventory | characterization.md |
| target-architecture | TAR | dependency-map, characterization | target-architecture.md |
| migration-plan | MGP | target-architecture, characterization | migration-plan.md |
| migration-slice | MGS | migration-plan | migration-slice.md |
| conversion-record | CNV | migration-slice | conversion-record.md |
| equivalence-report | EQV | characterization, conversion-record, migration-slice | equivalence-report.md |
| cutover-plan | CUT | migration-plan, equivalence-report | cutover-plan.md |
| stabilization-report | STB | cutover-plan | stabilization-report.md |
| user-stories | USR | unit-of-work | user-stories.md |
| prfaq | PRF | intent | prfaq.md |
| risk-register | RSK | intent | risk-register.md |
| measurement-criteria | MSR | intent | measurement-criteria.md |
| bolt-plan | BLT | unit-of-work, user-stories | bolt-plan.md |
| logical-design | LGD | domain-model, requirements | logical-design.md |
| deployment-units | DPU | implementation-plan | deployment-units.md |
| plan | PLN | any | plan.md |

The eight kinds from `user-stories` to `plan` are optional and gate-neutral: no gate requires them, so existing projects and samples are unaffected, and a team or depth profile opts in by requiring them. They cover the elaboration outputs, Bolts, design and deployment artifacts that the published AI-driven development method definition describes (see the [alignment table](../reference/aws-ai-dlc-mapping.md)).

Chain: intent -> unit of work -> requirements (criteria) -> architecture / test strategy (coverage) -> implementation plan (code and test references) -> deployment plan.

## Recommended context-memory layout

Artifacts are durable context for later steps, so keep them where people and AI can find them. A convention that works with any repository (all paths are relative to the project root and registered as `repo://` URIs):

| Folder | Holds |
|---|---|
| `ai-sdlc/plans/` | `plan` and `bolt-plan` artifacts with their approvals |
| `ai-sdlc/requirements/` | `intent`, `requirements`, `user-stories`, `risk-register`, `measurement-criteria`, `prfaq` |
| `ai-sdlc/design/` | `unit-of-work`, `domain-model`, `logical-design`, `architecture`, `threat-model` |
| `ai-sdlc/delivery/` | `test-strategy`, `implementation-plan`, `deployment-units`, `deployment-plan`, `operational-readiness` |
| `ai-sdlc/profiles/` | active-profile records |

The layout is a recommendation; Core and the validators do not depend on it.

## Deterministic checks

`check_traceability` fails with stable codes: `trace.duplicate_id`, `trace.missing_parent`, `trace.dangling`, `trace.parent_kind`, `trace.uncovered_criterion`, `trace.unknown_criterion`. Artifact parsing fails with `artifact.front_matter`, `artifact.schema`, `artifact.kind`, `artifact.version`, `artifact.missing_section`, `artifact.id`, `artifact.trace_format`, `artifact.criterion`.

## Notes

- Every artifact kind required by a gate has a template (tested). `build-verified` now requires `implementation-plan` (previously `implementation`): the plan is updated with code and test references as work is delivered.
- Core gates check registered base obligations. Modernization adds local parsing, traceability and digest checks through its transition wrapper; other artifact validators remain explicit local checks.
- Code/test evidence and deployment linkage are expressed through the implementation-plan and deployment-plan references; evidence records themselves stay in Core.
