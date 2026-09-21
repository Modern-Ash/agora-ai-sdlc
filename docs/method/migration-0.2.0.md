# AI-SDLC Method Pack 0.2.0 migration

Method Pack 0.2.0 is shipped as a **selectable candidate** alongside the existing 0.1.0 pack. This issue does not switch existing adoption profiles or samples to 0.2.0.

## Explicit selection

Python callers can resolve a packaged version with:

```python
from agora_ai_sdlc.method_versions import method_pack_path

current = method_pack_path("0.1.0")
candidate = method_pack_path("0.2.0")
```

The lifecycle harness also accepts an explicit version:

```python
Lifecycle(project, home)  # 0.1.0
Lifecycle(project, home, method_version="0.2.0")  # candidate
```

Unknown versions fail closed.

## Lifecycle changes

| Concern | 0.1.0 | 0.2.0 candidate |
| --- | --- | --- |
| States | readiness, intent, inception, construction, operations, completed | inception, construction, operations, completed |
| Initial state | readiness | inception |
| Terminal state | completed | completed |
| Forward gate 1 | readiness-approved / intent-framed / architecture-approved across early transitions | inception-approved |
| Forward gate 2 | build-verified | construction-verified |
| Final gate | completion | completion |
| Rework | gated rework-recorded transitions | ungated construction->inception and operations->construction, recorded by Core transition history |
| Required roles | product-owner, architect, builder, operator, quality-reviewer | product-owner, developer |
| Optional roles | none | quality-reviewer |

`completed` remains an Agora terminal recording state rather than a fourth delivery phase.

## Readiness and Intent

Removing `readiness` and `intent` from the 0.2.0 state machine does **not** remove their concepts or artifacts. Readiness assessment and product Intent remain flavor-level inputs/capabilities. In the candidate lifecycle they are prepared and consumed within or before Inception instead of being represented as separate work states.

## Gate baseline in this candidate

The 0.2.0 candidate deliberately focuses on lifecycle shape and role simplification.

- `inception-approved` currently requires Intent, Unit of Work, requirements, elaborated criteria, resolved clarifications and Product Owner + Developer approval.
- `construction-verified` currently requires domain model, architecture, implementation plan, test strategy, verified criteria, successful test-suite evidence and Developer approval.
- `completion` requires operational readiness, rollback procedure, accepted criteria, deployment/security evidence and Product Owner acceptance.

Later issues extend this baseline:

- #99: first-class Level 1 / Level-N plan artifacts and approval semantics.
- #100: adaptive pathway planning and conditional execution depth.
- #101: first-class executable Bolts.

Therefore 0.2.0 should not yet be described as completing those capabilities merely because the three-phase lifecycle is available.

## Migration strategy

Existing projects and profiles remain on 0.1.0 until explicitly upgraded. A migration should:

1. finish or checkpoint work that is currently in `readiness` or `intent`;
2. map active early work into `inception`;
3. replace role assignments for architect/builder/operator with the base `developer` role where appropriate;
4. update automation that references old gate ids;
5. re-evaluate profile-specific obligations against the new three-gate baseline;
6. validate the candidate in a non-production project before changing an adoption profile's pinned method version.

No in-place state rewrite is performed by this release.
