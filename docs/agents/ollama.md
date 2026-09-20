# Ollama (small-context models)

Assumes a small context window. Rules from [AGENTS.md](../../AGENTS.md) still apply.

- **Mandatory context:** AGENTS.md, `TASK.md`, and explicitly supplied files. Nothing is discovered by exploring.
- **Hand over explicitly:** each file in *Allowed paths* and any named contract.
- One small task per session; recommended maximum ~5 files touched.
- No implicit architectural decisions; if information is missing, write a `CLARIFICATION` and stop.
- Output must be structured: complete `RESULT.md` and `TESTS.md` using the templates.
- Use `context:small` tasks only.
