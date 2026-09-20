# Contributing

## Setup and verification

```bash
uv sync
uv run python scripts/verify_all.py
```

The verification script runs, in order: lint, format check, tests, local Markdown links, flavor manifest validation, pack validation, samples and a wheel-install smoke test. It stops at the failing phase and prints a recovery command. It needs no network after dependencies are installed. Packs and samples phases report "nothing to validate" until issues #13 and #21 add content.

## Rules (humans and agents)

- Read [AGENTS.md](AGENTS.md) first; scope comes from the issue and its `TASK.md`.
- Inspect before editing; preserve repository boundaries ([docs/repository-boundaries.md](docs/repository-boundaries.md)).
- Add failure-path tests for fail-closed behavior.
- Never add credentials, tokens or provider SDK dependencies.
- Conventional Commits; one issue per PR ([docs/development/pull-requests.md](docs/development/pull-requests.md)).
