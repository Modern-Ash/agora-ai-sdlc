---
schema: "agora-ai-sdlc/artifact/v1"
kind: "plan"
version: 1
id: ""
work: ""
revision: 1
traces-to: []
level: 1
parent-plan: null
intent: ""
unit: null
proposed-by: ""
approval-state: "pending"
approved-by: null
approved-revision: null
steps: []
required-sections: ["Scope", "Level and parent", "Steps", "Approval"]
---
# Plan

## Scope

Describe the Intent and optional Unit covered by this Plan.

## Level and parent

Record the Plan Level and parent plan relationship. Level 1 has no parent. Level N plans must trace to their Level N-1 parent.

## Steps

Ordered execution decisions. Each step records execute/skip, rationale, dependencies, and required/produced artifacts.

## Approval

Record approval state, accountable human approval, and the artifact revision approved before execution.
