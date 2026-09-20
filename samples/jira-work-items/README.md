# Jira work-item sample

Runs the Jira profile against a deterministic work-item fixture. It installs Core's reviewed read-only adapter, prepares a read without launching `acli`, demonstrates a denied transition, records bounded evidence, and completes an offline Agora lifecycle without treating Jira status as Agora lifecycle state.

```bash
uv run agora-ai-sdlc run-sample jira-work-items
```

No Jira account, network access, or credentials are used.
