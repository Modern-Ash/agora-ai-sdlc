# Verification — issue 166

Executed on 2026-09-22 against the implementation in this branch. Local Python: CPython 3.13.5, Linux. Formatter: Ruff 0.16.8. No product credentials or live model calls were used.

## Reproducible environments

A temporary branch-only workflow archived tracked source and downloaded public dependency wheels. Its source archive Git tree matched the downloaded source tree before editing. Two isolated environments used Core 0.9.1 and Core 0.8.2 respectively. Both were configured to import the working source as a development installation, rather than an older installed wheel. No test was weakened to accommodate that setup.

The dedicated wheel test builds a real wheel, extracts it outside the repository, explicitly checks that the imported module belongs to that extraction, and verifies skill resource bytes/hashes against source. It does not pass by silently importing the development source.

## Commands and outcomes

Standard online project setup:

```bash
uv sync --python 3.13
uv run python scripts/verify_all.py
```

Actual local offline execution used the preinstalled environments and dependency wheel directory:

```bash
PATH=/mnt/data/dev/venv166/bin:$PATH \
UV_OFFLINE=1 UV_FIND_LINKS=/mnt/data/dev/validation-bundle/wheels \
UV_NO_BUILD_ISOLATION=1 UV_PROJECT_ENVIRONMENT=/mnt/data/dev/venv166 UV_NO_SYNC=1 \
/mnt/data/dev/venv166/bin/python scripts/verify_all.py
```

Repeated with `venv166-core082` in place of `venv166` for the minimum supported Core.

| Check | Core 0.9.1 | Core 0.8.2 |
| --- | --- | --- |
| Complete pytest suite | 896 passed, 2 skipped | 877 passed, 21 skipped |
| Lint and formatter | PASS | PASS |
| Documentation links | PASS | PASS |
| Flavor manifest | PASS | PASS |
| Marketplace compatibility evidence | PASS | PASS |
| Method Pack validation | PASS, 1 pack | PASS, 1 pack |
| Bundled samples | PASS, 18 samples | PASS, 18 samples |
| Package / wheel smoke test | PASS | PASS |
| verify_all final result | all phases passed | all phases passed |

## Regression coverage

- Detail/language changes leave the compact machine snapshot byte-identical, even with stdout and stderr captured together.
- A separate UI file receives rich output while stdout remains compact JSON.
- Start progress leaves the returned contract and handoff bytes unchanged.
- Missing exact Work does not substitute `first-work`; read errors and races remain explicit.
- Real Core observation leaves the project's durable governance files byte-identical.
- Unreported usage remains unknown; recorded zero and measurement basis remain distinct.
- Raw command/context/exception contents are excluded; metadata redaction and terminal-control removal tested.
- File isolation, symlink refusal, exclusive creation, bounded output, watch intervals and cancellation tested.
- Only root plus selected phase load; full resources installed; unrelated skill files preserved; built-wheel resource hashes match source.

## Not claimed

Local Python 3.11/3.12 and hosted CI were not executed by the local command above; consult the PR checks for those environments. No live user Agorix workspace, provider billing, actual external-agent process tracking or independent human/agent review was tested. UI redaction is not a complete PII detector. No percentage of token savings is claimed.
