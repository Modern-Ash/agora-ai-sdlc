# Fidelity plan: Method Pack 0.2.0 against the published method definition

Decision (2026-09-21): Agora AI-SDLC follows the published AI-Driven Development Lifecycle method definition (the AWS blog post and the paper by Raja SP, cited in the [alignment table](aws-ai-dlc-mapping.md)) as faithfully as Agora Core allows. Where the current Method Pack differs from the paper, the paper wins unless Core cannot express it, and every remaining difference is listed here as a forced or additive deviation. This document is a plan and a decision record, not shipped behavior. Content is paraphrased; no text or prompts from the sources are reproduced. AWS is methodological inspiration, not a runtime dependency or endorsement; the project is not affiliated with AWS.

## Implementation status

Method Pack 0.2.0 is shipped under `registry/method-versions/ai-sdlc/0.2.0` and is the Method Pack used by the current project installer. The 0.1.0 pack remains available for existing projects and compatibility. The 0.2.0 gate contract now requires the core Inception outputs (Level 1 Plan, Stories, NFRs, Risk Register, Measurement Criteria, Units and Bolts) and the Construction gate requires Domain Design, Logical Design, implementation/test artifacts and a Deployment Unit. Recursive plans, adaptive pathways and executable Bolts are implemented by the flavor around the Method Pack.

## What the paper defines, and the target

| Element in the paper | Today | Target in Method Pack 0.2.0 |
| --- | --- | --- |
| Three phases: Inception, Construction, Operations | six states: `readiness`, `intent`, `inception`, `construction`, `operations`, `completed` | states `inception`, `construction`, `operations`, `completed`; `readiness` and `intent` disappear as states |
| A Level 1 Plan is generated for the pathway and validated by humans before the phases begin; steps decompose recursively into Level 2 and deeper | none | a `plan` artifact (Level 1) approved at the start of Inception; sub-plans are further `plan` artifacts traced to their parent; approval before execution is a gate requirement |
| Intent is the starting artifact of Inception | separate `intent` state and gate | `product-intent` is an Inception artifact, not a state |
| Mob Elaboration: clarify, elaborate stories, NFRs and risks, compose Units, optional PRFAQ, validate | continuous wizard implemented | outputs are first-class artifacts and required by the 0.2 Inception gate; PRFAQ remains optional |
| Inception outputs: PRFAQ (optional), user stories, NFR definitions, risk descriptions, measurement criteria traced to the intent, suggested Bolts | implemented | first-class templates/contracts; all are required by `inception-approved` except optional PRFAQ |
| Construction: Domain Design, then Logical Design with ADRs, then code and unit tests, then testing; brown-field first elevates code into static and dynamic models | implemented contract | `domain-model`, `logical-design`, implementation/test and `deployment-unit` are required by `construction-verified`; brownfield semantic elevation remains enforced by the flavor |
| Mob Construction: teams exchange integration specifications and deliver Bolts | not defined | ritual named Mob Construction |
| Operations: Deployment Units tested for function, security and non-functional requirements; deployment, observability, human-approved actions | partial | Deployment Units artifact plus deployment and security evidence |
| Minimal roles: Product Owner and Developers; QA and stakeholders join the mob | nine roles, five required | required roles: `product-owner`, `developer`; `quality-reviewer` recommended; governance roles become optional extensions outside the base method |
| Human validation at each step ("loss function") | gates plus continuous wizard confirmations | phase gates remain authoritative while the wizard introduces meaningful validation points throughout artifact enrichment |
| Bolts: hours or days, planned by AI, validated by humans; a Unit is executed by one or more Bolts, in parallel or in sequence | template section and a `bolt-plan` artifact | `bolt-plan` per Bolt, required in Inception (suggested) and before each Construction Bolt (approved) |
| Persisted, linked artifacts as context memory with backward and forward traceability | traced Markdown artifacts plus Context Graph | retained and extended with bounded context selection and fail-open Context Economy |
| No hard-wired workflow per pathway (greenfield, brownfield, refactor, defect, scaling) | fixed chain | pathway-specific plans instead of pathway-specific state machines; the state machine stays the three phases |
| Design technique integral to the method; a DDD flavor first | `domain-model` template | the base flavor is the DDD flavor; other techniques (BDD, TDD) are named later flavors, not built now |

## Deviations that remain, and why

1. **`completed` state.** Agora Core requires a terminal state; the paper has none. `completed` records operational acceptance after Operations and adds no phase or ritual.
2. **Fail-closed gates.** The paper relies on human oversight; Agora also refuses a transition without recorded evidence. This strengthens, and does not contradict, the paper's validation checkpoints.
3. **Governance extensions.** Segregation of duties, independent review profiles, data eligibility, model provenance, budgets, signed actions and the Regulated profile are outside the paper. They stay opt-in and never change phase names or rituals.
4. **Provider neutrality.** The paper illustrates examples with one cloud's services and one model API. Those are examples, not method; Agora stays provider-neutral. Its appendix prompts are not reproduced; Agora ships its own provider-neutral facilitation guidance.
5. **Rework transitions.** Construction to Inception and Operations to Construction are kept because the paper describes the method as iterative; they are ungated and recorded.

## Target lifecycle and gates

States `inception -> construction -> operations -> completed`, with ungated rework `construction -> inception` and `operations -> construction`.

| Gate (transition) | Required artifacts | Required evidence and approvals |
| --- | --- | --- |
| `inception-approved` (inception to construction) | approved `plan` (Level 1), `intent`, `plan`, `requirements`, `user-stories`, `nfr`, `risk-register`, `measurement-criteria`, `unit-of-work`, suggested `bolt-plan` | clarifications resolved; `product-owner` and `developer` approvals; criteria at `elaborated` |
| `construction-verified` (construction to operations) | `domain-model`, `logical-design`, `implementation-plan`, `test-strategy`, `deployment-unit` | successful `test-suite` evidence; criteria at `built` and `verified`; `developer` approval and `quality-reviewer` approval where that role is assigned |
| `completion` (operations to completed) | `operational-readiness`, `rollback-procedure` | successful `deployment` and `security-scan` evidence; criteria at `deployed` and `accepted`; `product-owner` approval |

Depth profiles keep tuning strictness on top of these obligations; the base method is the paper's, not a lighter or heavier variant.

## Impact

The rewrite breaks the current Method Pack contract (state names, gate names, role names) while the flavor is still 0.x:

- Method Pack: `METHOD.md`, protocol, roles, six gates, eight transitions, and the criterion-stage roles.
- Flavor code and assets: depth profiles, artifact traceability roots, role conformance, independent-review and provenance defaults, the Studio projection presentation labels, Starter, Enterprise, Modernization, Regulated and pilot samples, and the scenario harness that most tests use. A repository search finds about 60 files that use the current `readiness` state, 30 that use the current role names and 20 that use the current gate names.
- Other repositories: Agora Studio tests and fixtures that expect the current state ids (Studio itself renders states generically); the published projection fixtures.
- Documentation and commercial packages that describe the six-state lifecycle, and the closed epic #2 deliverables.

## Sequence

1. Keep 0.1.0 packaged unchanged for compatibility.
2. Validate the enriched 0.2.0 gates and artifact contracts with the full verification suite.
3. Exercise the continuous wizard end-to-end on representative greenfield and brownfield Works, including Context Economy measurements.
4. Update Studio/projection fixtures and commercial collateral to surface the same three-phase vocabulary and method outputs.
5. Publish the migration/release note only after CI and pilot evidence are green; existing 0.1.0 projects remain upgrade-controlled.

## Open questions

- **Naming.** Adopt the paper's ritual names (Mob Elaboration, Mob Construction) in the method text for fidelity, accepting the third-party-term risk noted in the competitive positioning note, or keep descriptive names. Current documents use descriptive names; fidelity favors the paper's, pending legal review.
- **Role for AI.** The paper treats AI as a collaborator rather than a role; in Agora an AI actor fills the `developer` or another role and the accountable human stays recorded. Confirm that is the intended reading.
- **Quality reviewer.** Required or recommended. The paper names QA as a mob participant but not as a gate role.
