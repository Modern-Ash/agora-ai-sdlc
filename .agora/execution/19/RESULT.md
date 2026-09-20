---
issue: 19
status: partial
pull_request: pending
---
# Result
15 schema-versioned templates, `agora_ai_sdlc.artifacts` (parse/validate/traceability), `docs/method/artifacts.md`, tests.

## Decisions / deviations
- Gate kind `implementation` renamed `implementation-plan` (template listed by the issue); tests/docs updated.
- Traceability id scheme `PREFIX-NNN` and the parent-kind table are my design; confirm.
- Criterion ids are Core criterion slugs, not `CRIT-` ids.
- Validators are standalone: not enforced by gates, and templates are not yet checked by verify_all beyond tests.
- Earlier short templates from #17/#18 were replaced by the versioned ones.
- Not verified: that an LLM can fill templates from the docs.
