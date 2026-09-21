# Risk and issue management

Agora AI-SDLC uses a provider-neutral record contract for delivery risks and active issues. The contract does not require Jira, GitHub Issues, ServiceNow, or any other tracker.

Each record captures accountable ownership, severity, state, scope and evidence. Risks additionally declare probability and mitigation. Issues declare the next action required to resolve the active problem. Resolved or closed records require evidence.

The evaluator is deterministic and offline. Opaque logical references such as `repo://...`, `evidence:...` or `tracker:...` are allowed. Raw network endpoints and credential-bearing references are rejected.

A portfolio summary reports total, open and blocking records plus deterministic ids for open high/critical blockers. External trackers may map into this contract, but they remain authoritative for their own source facts.
