# Construction — bounded, authorized execution

Before exploratory repository reads, build the deterministic bounded context with `aisdlc execution-bundle --root . --swarm <swarm> --work <work> --json`. Use its objective, acceptance criteria, related paths, branch/base/HEAD, verification commands and mechanical risk flags as the default Construction context. Expand beyond that bundle only when an explicit unresolved need remains; do not repeat broad `find`, `grep`, `git status`, build-tool discovery or repository inventory work already represented by the bundle.

Read the exact Work/revision, approved scope, allowed paths, Plan and Bolt Plan.
Check structure, pathway applicability, references and current Core readiness.
Use the installed Plan and Bolt validators. `parse_bolt_plan` succeeding does not
authorize execution: `assert_can_start` must pass for the next Bolt, its current
approved revision, dependencies and lifecycle state. A pending Bolt Plan blocks
the affected execution even if a conversational message says "continue".

Never fabricate approval or record completion retroactively to hide a bypass.
Never treat an observation or a skill instruction as a Core authorization.
When the governed runner cannot enforce the requested boundary, report that
limitation; do not launch an unrestricted process as a substitute.

Within explicit authorization, group mechanical work and validation. Escalate a
new product choice, conflicting decisions, changed scope, missing authority,
security/data-policy issue, or exhausted execution budget. Do not ask the human
to transport findings or repeat already valid decisions.

Anticipate the next validation/review: prepare its bounded inputs and evidence
references while finishing the authorized work. Never enter another phase or
spend resources outside the delegation just to "get ahead". No synthetic progress
percentage, unverifiable live-runtime status, or inferred token/cost number.

For read-only visibility use `aisdlc observe --swarm <swarm> --work <work> --json`.
Do not put an observation watch loop in an agent's conversation. A human/host can
run `observe --watch --ui-file <new-file>` separately; its UI stream is not model
context. Query a fresh compact snapshot only when needed for the next action.
