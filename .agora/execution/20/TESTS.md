---
issue: 20
tested_commit: working tree on main (post PR #54)
timestamp: 2026-09-20
---
# Tests
`uv run python scripts/verify_all.py` passes; 170 tests. `tests/test_depth_profiles.py`: golden obligation snapshots for all 4 depths; standard == pack baseline; determinism; monotonicity chain (and reversed fails); only minimal removes and is justified; protected removal and unjustified removal rejected; unknown profile (incl. empty string) rejected; CLI; read-only assess; mid-work stricter depth against real Core (work unchanged, Core still moves on baseline); depth recommendation table. Wheel contains profiles/depth.
Bug found by the tests and fixed: an empty depth string silently resolved to the baseline.
Not executed: signed-action enforcement for regulated (declared only); Python 3.11/3.13; CI.
