---
issue: 10
status: complete
pull_request: pending
---
# Result

Hatchling package `agora-ai-sdlc` (src layout, Python >=3.11), `agora-ai-sdlc --version`, asset dirs (registry, profiles, policies, templates, samples) force-included in wheel and sdist, CHANGELOG, .gitignore, uv.lock, pytest tests.

## Decisions
- Core range `agora-framework>=0.8.2,<0.9` (latest released is 0.8.2). Assumption to validate.
- Asset dirs hold placeholder READMEs until later issues populate them.
- Not done (belongs to #14): CI matrix, verify_all.py, lint. README editable-setup docs added.

## Risks
Independent review pending.
