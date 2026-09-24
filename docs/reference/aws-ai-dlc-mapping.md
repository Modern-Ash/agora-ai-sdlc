# Public AWS AI-DLC concept mapping and alignment

Sources: the public AWS DevOps Blog post "AI-Driven Development Life Cycle" (`https://aws.amazon.com/blogs/devops/ai-driven-development-life-cycle/`) and the public "AI-Driven Development Lifecycle (AI-DLC) Method Definition" paper by Raja SP (Amazon Web Services), published as a PDF at `https://prod.d13rzhkk8cj2z0.amplifyapp.com/aidlc.pdf` (reviewed 2026-09-21). Concepts are compared in our own words; no text or prompts from either source are reproduced. AWS is methodological inspiration, not a runtime dependency or endorsement, and this project is not affiliated with AWS.

Goal: stay as close to the published AI-DLC method as possible while keeping this flavor provider-neutral and Core-governed. Status uses: **aligned**, **partial**, **gap**, and **deliberate difference** (a governance addition that the method does not define).

## Principles

| AI-DLC principle | Status | Agora AI-SDLC |
| --- | --- | --- |
| AI initiates and directs the conversation; humans approve at critical junctures | aligned | [Protocol](../../registry/methods/ai-sdlc/PROTOCOL.md): plan, clarify, human decision, execute, validate; clarifications and gates enforced by Core |
| Human validation at each step catches errors early | aligned | Gates require evidence and accountable approvals before each forward transition |
| Persist every artifact as durable context memory, with backward and forward traceability | aligned | Markdown artifacts in Git with `traces-to` links and the [traceability engine](../method/artifacts.md) |
| Three phases: Inception, Construction, Operations | aligned | Method Pack 0.2.0 uses `inception -> construction -> operations -> completed`; `completed` is only the Core terminal record |
| Retain user stories as the contract between humans and AI | aligned | First-class `user-stories` artifact plus acceptance criteria traceability |
| Design techniques integral to the method (a DDD flavor first) | aligned | Construction now distinguishes `domain-model` (Domain Design) and `logical-design`; broader architecture/ADR artifacts remain compatible |
| Minimal roles (Product Owner and developers) | deliberate difference | Nine roles for governance and segregation of duties; small teams may hold several |
| No hard-wired workflow: AI proposes a Level 1 Plan per pathway, recursively decomposed | aligned | Method Pack 0.2.0 keeps only the three phases; first-class recursive `plan`, adaptive pathway policy and Bolt decomposition live in the flavor |
| Bolts replace sprints (hours or days), Units of Work replace epics | aligned | `unit-of-work` and `bolt-plan` are first-class, traced artifacts; the 0.2 Inception gate requires both |
| Retain risk practices (Risk Register) | aligned | First-class `risk-register` artifact is part of the 0.2 Inception contract |
| Brown-field: elevate code to static and dynamic models before construction | aligned | `static-system-model` and `dynamic-system-model` artifacts; `plan-validate --artifacts` enforces them for pathways that require elevation |

## Phases, rituals and artifacts

| AI-DLC element | Status | Agora AI-SDLC | Proposed action |
| --- | --- | --- | --- |
| Intent | aligned | `product-intent` artifact, state `intent` | none |
| Mob Elaboration (collaborative elaboration of Intent into stories, criteria and Units) | aligned | continuous wizard drives clarification and progressive Inception enrichment in one governed session | wizard is the executable facilitation surface |
| User stories and acceptance criteria | aligned | `user-stories`, requirements criteria and deterministic traceability | — |
| Non-functional requirements | aligned | first-class `nfr` artifact, linked into Logical Design and test strategy | — |
| PRFAQ (optional) | aligned | optional `prfaq` artifact/template; not required by the Inception gate | — |
| Risk descriptions (matching an organization's Risk Register) | aligned | first-class `risk-register` artifact and Inception gate obligation | — |
| Measurement criteria traced to the business intent | aligned | first-class `measurement-criteria` artifact traced from requirements/stories/Unit | — |
| Units and suggested Bolts | aligned | `bolt-plan` artifact, `agora_ai_sdlc.bolts` | — |
| Mob Construction (collocated teams exchanging integration specifications) | partial | continuous Construction wizard and governed sessions implement the interaction pattern; physical co-location is intentionally not required | document team ritual guidance separately |
| Domain Design | aligned | `domain-model` template | none |
| Logical Design with architecture decision records | aligned | first-class `logical-design` artifact with NFR mapping, trade-offs and decisions; architecture/ADRs remain compatible | — |
| Code and unit tests generated, executed and analyzed | aligned | build evidence and `test-suite` evidence at `build-verified` | none |
| Deployment Units tested for function, security and non-functional requirements | aligned | first-class `deployment-unit` plus test/security/deployment evidence contracts | — |
| Operations: telemetry analysis, runbooks, human-approved actions | aligned | operational-evidence profile and control bands | none |
| Context-memory folder layout for plans, requirements, stories and designs | gap | artifacts live at project-chosen paths | publish a recommended layout in [artifacts](../method/artifacts.md) |
| Plans with checkboxes, approved before execution | aligned | recursive `plan` artifacts and 0.2 Inception gate require the Level 1 Plan before Construction | — |

## Deliberate differences

These additions are outside the published method and remain: evidence-based gates enforced by Core, explicit `readiness` and `intent` states, producer/reviewer separation profiles, data-classification and runtime-eligibility policy, model provenance, budgets and fallback, signed actions and the Regulated profile, adoption profiles, and the Studio projection. They add governance the method leaves to the adopting organization; they do not change its phase names or rituals.

## Open alignment decisions

1. **Mob Construction ritual.** The workflow mechanics are implemented, but the paper's co-located team ritual is a facilitation practice rather than a Core lifecycle requirement; document it as adoption guidance rather than enforcing physical co-location.\n2. **Role extensions.** Method Pack 0.2.0 keeps Product Owner + Developer as the base roles while profiles may add quality/security/governance roles without changing the base method.\n3. **Promotion evidence.** Keep 0.1.0 available for existing projects; validate the enriched 0.2.0 gates, wizard and samples before declaring a release-level fidelity claim.


## Machine-readable fidelity rules

Issue #96 turns this mapping into deterministic repository checks. The rule contract is
`contracts/conformance/aws-original-rules-v1.yaml`; it maps every capability declared by the
`aws-original` compatibility profile to explicit Agora artifacts, Method Pack fields, templates, source modules, or documentation evidence.

The rule provider reports `PASS`, `PARTIAL`, or `FAIL` for required base-method capabilities and leaves absent optional capabilities as `NOT_APPLICABLE`. Agora-specific governance additions are listed separately as `agora-additive` and are deliberately excluded from the base-method fidelity result.
