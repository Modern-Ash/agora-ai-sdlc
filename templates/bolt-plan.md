---
schema: "agora-ai-sdlc/artifact/v1"
kind: "bolt-plan"
version: 1
id: ""
work: ""
revision: 1
traces-to: []
unit: ""
plan: null
proposed-by: ""
approval-state: "pending"
approved-by: null
approved-revision: null
bolts: []
required-sections: ["Scope", "Bolts", "Conflicts", "Approval"]
---
# Bolt Plan

## Scope

Name the Unit of Work delivered by these Bolts and, optionally, the approved Plan that authorizes them.

## Bolts

Ordered Bolts. Each records id, mode (sequential or parallel), status, tasks, dependencies, written paths, produced artifacts and evidence links.

## Conflicts

Record how parallel Bolts are kept independent: distinct write sets or an explicit dependency between them.

## Approval

Record approval state, accountable human approval and the exact revision approved before any Bolt runs.
