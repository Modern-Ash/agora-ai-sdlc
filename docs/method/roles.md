# AI-SDLC roles

Roles live in [registry/methods/ai-sdlc/roles](../../registry/methods/ai-sdlc/roles). A role is an **accountability** slot; the actor filling it (human, AI agent or swarm) is only the **execution**. Delegating to AI never removes the accountable human recorded in the swarm assignment.

| Role | Kinds | Key authority | Notable limits |
|---|---|---|---|
| product-owner | human, ai-agent | Approves intent, design, completion; accepts criteria | No waivers |
| domain-expert | human, ai-agent | Clarifications and artifacts | Advisory: no transition, no approval |
| architect | human, ai-agent, swarm | Design, approves design, inception transitions | |
| builder | human, ai-agent, swarm | Marks criteria built | Never approves; no merge/release/deploy |
| quality-reviewer | human, ai-agent | Verifies criteria, approves build gate | Independent of producer |
| security-reviewer | human, ai-agent | Evidence and approvals in security gates | No transitions |
| operator | human, ai-agent | Marks deployed | Deploy needs explicit environment grant |
| ai-orchestrator | ai-agent, swarm | Assign, decompose, delegate, block | No approvals, gates or transitions |
| governance-owner | human | Waive gates, cancel, reopen | Human-only |

## Combinations

- **Small team / Starter:** one human plus one AI may hold all five required roles, provided the builder's output is approved by a different role-holder identity where the profile demands independence (profiles #32, policies #22).
- **Prohibited in Regulated profile (to be enforced by #22/#34):** builder with quality-reviewer or security-reviewer on the same change; product-owner with governance-owner for an exception on its own work; any AI actor as governance-owner (already enforced by actor kinds).

## Scope of what is verified

`tests/test_role_conformance.py` checks role files structurally: every transition, gate approval and criterion stage has an authorized role; no role has universal authority; only governance-owner waives, cancels or reopens; the builder never approves. Live execution through Core (human, AI and delegated actors) is not yet exercised; it needs the end-to-end sample (#21).
