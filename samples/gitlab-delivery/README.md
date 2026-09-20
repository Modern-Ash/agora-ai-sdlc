# GitLab delivery sample

Runs the GitLab profile against a deterministic issue, merge-request, and pipeline fixture. It installs Core's reviewed read-only adapters, prepares read operations without launching `glab`, demonstrates a denied write, records bounded evidence, and completes an offline Agora lifecycle.

```bash
uv run agora-ai-sdlc run-sample gitlab-delivery
```

No GitLab account, network access, or credentials are used.
