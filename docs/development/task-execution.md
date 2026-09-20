# Task execution

1. Select a `ready` issue.
2. Create `.agora/execution/<issue>/` (per issue, at implementation time only).
3. Generate `TASK.md` from [the template](../../.agora/templates/TASK.md) (Planner).
4. Resolve clarifications (`CLARIFICATION-<n>.md`); stop if unanswered.
5. Implement within *Allowed paths* (Implementer).
6. Record checks in `TESTS.md`.
7. Summarize in `RESULT.md`.
8. Independent review (Reviewer).
9. Record the verdict in `REVIEW.md`.
10. Open or update the pull request.
11. Close the issue only after its criteria are verified.

Templates: [.agora/templates/](../../.agora/templates/). Roles: [planner](../agents/planner.md), [implementer](../agents/implementer.md), [reviewer](../agents/reviewer.md).
