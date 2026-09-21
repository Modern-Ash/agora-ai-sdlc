# Public AWS AI-DLC concept mapping and alignment

Sources: the public AWS DevOps Blog post "AI-Driven Development Life Cycle" (`https://aws.amazon.com/blogs/devops/ai-driven-development-life-cycle/`) and the public "AI-Driven Development Lifecycle (AI-DLC) Method Definition" paper by Raja SP (Amazon Web Services), published as a PDF at `https://prod.d13rzhkk8cj2z0.amplifyapp.com/aidlc.pdf` (reviewed 2026-09-21). Concepts are compared in our own words; no text or prompts from either source are reproduced. AWS is methodological inspiration, not a runtime dependency or endorsement, and this project is not affiliated with AWS.

Goal: stay as close to the published AI-DLC method as possible while keeping this flavor provider-neutral and Core-governed. Status uses: **aligned**, **partial**, **gap**, and **deliberate difference** (a governance addition that the method does not define).

## Principles

| AI-DLC principle | Status | Agora AI-SDLC |
| --- | --- | --- |
| AI initiates and directs the conversation; humans approve at critical junctures | aligned | [Protocol](../../registry/methods/ai-sdlc/PROTOCOL.md): plan, clarify, human decision, execute, validate; clarifications and gates enforced by Core |
| Human validation at each step catches errors early | aligned | Gates require evidence and accountable approvals before each forward transition |
| Persist every artifact as durable context memory, with backward and forward traceability | aligned | Markdown artifacts in Git with `traces-to` links and the [traceability engine](../method/artifacts.md) |
| Three phases: Inception, Construction, Operations | partial | Same phases, plus extra `readiness` and `intent` states before Inception and a terminal `completed` state |
| Retain user stories as the contract between humans and AI | gap | Acceptance criteria and `requirements` exist; there is no user-story artifact |
| Design techniques integral to the method (a DDD flavor first) | partial | `domain-model` and `architecture` templates exist; no technique-specific flavor or Domain/Logical Design split |
| Minimal roles (Product Owner and developers) | deliberate difference | Nine roles for governance and segregation of duties; small teams may hold several |
| No hard-wired workflow: AI proposes a Level 1 Plan per pathway, recursively decomposed | gap | Fixed six-state lifecycle; no plan artifact tied to a pathway |
| Bolts replace sprints (hours or days), Units of Work replace epics | partial | Both are defined terms; a Bolt is only a section of the `unit-of-work` template, not a recorded artifact |
| Retain risk practices (Risk Register) | partial | `risks` sections in intent and architecture; no organization risk-register linkage |
| Brown-field: elevate code to static and dynamic models before construction | partial | Modernization profile: legacy inventory, dependency map, characterization; no explicit static/dynamic model artifacts |

## Phases, rituals and artifacts

| AI-DLC element | Status | Agora AI-SDLC | Proposed action |
| --- | --- | --- | --- |
| Intent | aligned | `product-intent` artifact, state `intent` | none |
| Mob Elaboration (collaborative elaboration of Intent into stories, criteria and Units) | gap | not defined | document the ritual as a facilitated session recorded through Core sessions and gates |
| User stories and acceptance criteria | partial | acceptance criteria in Core; `requirements` template | add a `user-stories` artifact template |
| Non-functional requirements | aligned | `requirements` has a mandatory section | none |
| PRFAQ (optional) | gap | not defined | add an optional `prfaq` template |
| Risk descriptions (matching an organization's Risk Register) | partial | risks in `product-intent` and `architecture` | add a `risk-register` template with an external-reference field |
| Measurement criteria traced to the business intent | partial | `Success measures` in `product-intent` | add a `measurement-criteria` template and trace it from stories |
| Units and suggested Bolts | partial | `unit-of-work` template lists Bolts | record Bolts as first-class artifacts planned by AI and validated by a human |
| Mob Construction (collocated teams exchanging integration specifications) | gap | not defined | document the ritual; integration specifications as Unit artifacts |
| Domain Design | aligned | `domain-model` template | none |
| Logical Design with architecture decision records | partial | `architecture` has Decisions | add a `logical-design` template covering non-functional patterns and ADR links |
| Code and unit tests generated, executed and analyzed | aligned | build evidence and `test-suite` evidence at `build-verified` | none |
| Deployment Units tested for function, security and non-functional requirements | partial | `deployment-plan`, `test-strategy`, security-scan and deployment evidence | add a `deployment-units` template |
| Operations: telemetry analysis, runbooks, human-approved actions | aligned | operational-evidence profile and control bands | none |
| Context-memory folder layout for plans, requirements, stories and designs | gap | artifacts live at project-chosen paths | publish a recommended layout in [artifacts](../method/artifacts.md) |
| Plans with checkboxes, approved before execution | partial | `implementation-plan` template | add a `plan` template with approval checkpoints |

## Deliberate differences

These additions are outside the published method and remain: evidence-based gates enforced by Core, explicit `readiness` and `intent` states, producer/reviewer separation profiles, data-classification and runtime-eligibility policy, model provenance, budgets and fallback, signed actions and the Regulated profile, adoption profiles, and the Studio projection. They add governance the method leaves to the adopting organization; they do not change its phase names or rituals.

## Open alignment decisions

1. **Phase grouping.** The lowest-risk way to match the three-phase model is presentation: group `readiness`, `intent` and `inception` as the Inception phase, `construction` as Construction, and `operations` and `completed` as Operations, while Core keeps the six states for gate enforcement.
2. **Lifecycle shape.** Collapsing `readiness` and `intent` into Inception would match the method exactly but changes Method Pack states, gates, samples and the Studio contract, so it needs an explicit decision and a new Method Pack major version.
3. **Roles.** Reducing the role set toward Product Owner and developers would change authority matrices and segregation controls; keep the current roles unless the adopting team chooses a smaller profile.


## Machine-readable fidelity rules

Issue #96 turns this mapping into deterministic repository checks. The rule contract is
`contracts/conformance/aws-original-rules-v1.yaml`; it maps every capability declared by the
`aws-original` compatibility profile to explicit Agora artifacts, Method Pack fields, templates, source modules, or documentation evidence.

The rule provider reports `PASS`, `PARTIAL`, or `FAIL` for required base-method capabilities and leaves absent optional capabilities as `NOT_APPLICABLE`. Agora-specific governance additions are listed separately as `agora-additive` and are deliberately excluded from the base-method fidelity result.
