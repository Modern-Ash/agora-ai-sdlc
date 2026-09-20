# Optional Live Smoke Contract

Live provider calls are never part of default CI. Operators may opt in by capturing structured Codex and Claude outputs from their own authenticated environments. Keep credentials, prompts containing restricted data and endpoint URLs out of captures.

Place captures in a private directory as `codex.jsonl` and `claude.json`, using the same success envelope fields documented by the installed adapter. Then run:

```console
AGORA_AI_SDLC_LIVE_SMOKE_DIR=/private/captures \
  uv run pytest tests/conformance/runtimes/test_live_smoke.py -q
```

The contract normalizes both captures and checks only outcome, phase, artifact and non-negative token counts. Captures are not committed or copied into Agora project state. Passing this optional check describes only the tested local versions and credentials; it is not a general provider certification.
