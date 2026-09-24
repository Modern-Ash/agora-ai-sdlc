# AI-SDLC lifecycle

The canonical macro lifecycle follows the AI-DLC phases while keeping explicit preparation and terminal
states around them:

`readiness -> intent -> inception -> construction -> operations -> completed`.

The user-facing Agora Flow wizard presents the three AI-DLC phases — **Inception, Construction and
Operations** — and exposes the preparation/terminal Core states as provenance rather than inventing
additional methodology phases. See [AI-DLC method compatibility](ai-dlc-compatibility.md).

| Transition | Roles | Gate |
|---|---|---|
| readiness -> intent | product-owner | readiness-approved |
| intent -> inception | product-owner, architect | intent-framed |
| inception -> construction | architect | inception-ready |
| construction -> operations | quality-reviewer | build-verified |
| operations -> completed | product-owner | completion |
| inception -> intent (rework) | architect, product-owner | rework-recorded |
| construction -> inception (rework) | architect | rework-recorded |
| operations -> construction (rework) | builder, operator | rework-recorded |

## Human validation is continuous

AI-DLC human oversight is not a final review phase. Each meaningful artifact enrichment is a decision
point: AI proposes, humans validate/adjust, and the accepted output becomes richer context for the next
step. Agora implements those checkpoints through durable artifacts, clarifications, evidence, approvals
and Core gates. The wizard may streamline the interaction, but it never silently supplies human
authority.

## Inception

The `intent-framed` gate opens Inception only after the Intent is explicit, criteria are elaborated,
clarifications are current and the Product Owner has approved the framing.

The `inception-ready` gate controls Inception -> Construction. It requires the core AI-DLC Inception
outputs in the current Work revision:

- `requirements`
- `user-stories`
- `nfr`
- `risk-register`
- `measurement-criteria`
- Level 1 `plan`
- cohesive `unit-of-work`
- suggested `bolt-plan`

Clarifications must be resolved and the Architect plus Product Owner must validate the proposal.
`prfaq` is intentionally optional.

Domain Design and Logical Design are **not** Inception gates. The AI-DLC method places those activities
inside Construction.

## Construction

Construction progressively enriches validated Inception context into tested, operations-ready delivery:

1. brownfield work performs semantic elevation when applicable;
2. `domain-model` captures business logic independently of infrastructure;
3. `logical-design` applies NFRs, patterns and explicit trade-offs;
4. `implementation-plan` binds implementation work to the design and acceptance contract;
5. `test-strategy` plus successful `test-suite` evidence verifies the outcomes;
6. `deployment-unit` packages executable/configuration/evidence for Operations.

The `build-verified` gate requires those five Construction artifacts, criteria at `verified`, successful
`test-suite` evidence and Quality Reviewer approval before Operations.

The broader `architecture` artifact remains supported for compatibility with existing profiles and ADR
workflows, but it no longer substitutes for AI-DLC Domain Design + Logical Design in the canonical
transition.

## Operations

Operations remains responsible for deployment readiness, rollout, observability and learning. The
`completion` gate requires:

- `deployment-plan`
- `rollback-procedure`
- `operational-readiness`
- criteria accepted;
- successful `deployment` and `security-scan` evidence;
- Product Owner approval.

Observability integrations and learning records can enrich the operational loop without weakening the
production authority boundary.

## Retry, rework, new revision

- **Retry:** a gate rejected the move; state does not change. Fix the missing item and try again.
- **Rework:** an earlier phase must be revisited within the same revision. A `rework-record` preserves
  why the flow moved backward and which artifacts are affected.
- **New revision:** completed work is never mutated. Reopening creates a new revision and resets current
  criteria/artifacts/evidence while preserving history.

## Rework record

Register a `rework-record` with the reason, affected artifacts and requester. Core enforces the
artifact presence; content-level freshness remains an explicit review responsibility.

## Core limitations

- Approvals are Work-revision scoped rather than gate scoped in supported Core versions, so the wizard
  must not imply that an old approval is a newly captured decision.
- Gates enforce artifact kind presence, not semantic quality. Agora's artifact validators, traceability
  checks and human review provide the deeper contract.
- Evidence types/results are gate facts; severity/profile-specific security blocking is handled by the
  corresponding AI-SDLC profiles.
- Profile-specific obligations must remain additive and must not reinterpret the canonical
  Inception/Construction/Operations meaning.

Blockers remain transparent Core facts such as `missing-artifacts=[...]`,
`missing-approvals=[...]`, `unsatisfied=[...]` and stale clarifications. The wizard translates them
into a friendlier interaction while Details preserves the raw governance view.
