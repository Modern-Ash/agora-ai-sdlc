---
schema: "agora-ai-sdlc/artifact/v1"
kind: "bolt-plan"
version: 1
id: "BLP-001"
work: "feature"
revision: 2
traces-to: ["UOW-001", "PLN-001"]
unit: "UOW-001"
plan: "PLN-001"
proposed-by: "project:planner"
approval-state: "approved"
approved-by: "project:po"
approved-revision: 2
bolts:
  - id: "schema"
    mode: "sequential"
    status: "completed"
    tasks: ["Define the storage schema"]
    depends-on: []
    writes: ["src/schema/"]
    produces: ["IMP-001"]
    evidence: ["evidence:schema-tests"]
  - id: "api"
    mode: "parallel"
    status: "running"
    tasks: ["Implement the API handlers"]
    depends-on: ["schema"]
    writes: ["src/api/"]
    produces: []
    evidence: []
  - id: "ui"
    mode: "parallel"
    status: "approved"
    tasks: ["Implement the UI screens"]
    depends-on: ["schema"]
    writes: ["src/ui/"]
    produces: []
    evidence: []
  - id: "integrate"
    mode: "sequential"
    status: "approved"
    tasks: ["Wire API and UI together", "Run end-to-end checks"]
    depends-on: ["schema", "api", "ui"]
    writes: ["tests/e2e/"]
    produces: []
    evidence: []
required-sections: ["Scope", "Bolts", "Conflicts", "Approval"]
---
# Bolt Plan

## Scope

Unit UOW-001 delivered in four Bolts; `api` and `ui` run in parallel.

## Bolts

See front matter.

## Conflicts

`api` and `ui` write disjoint paths.

## Approval

Approved by project:po at revision 2.
