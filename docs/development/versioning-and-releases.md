# Versioning, compatibility and releases

## Versions

- **Flavor version** (`version` in the flavor manifest, `agora_ai_sdlc.__version__`) uses Semantic Versioning. While the major version is `0`, a minor bump may change contracts; every such change is recorded in [CHANGELOG.md](../../CHANGELOG.md).
- **Contract schemas** (`agora-ai-sdlc/.../v1`, `agora/flavor/v1`) are versioned independently in their id. Adding an optional field keeps `v1`; removing a field, changing a type or changing meaning requires a new major schema id ([Studio projection](../integrations/studio-projection.md#versioning) states the same rule for its aggregate).
- **Method Pack** versions follow the flavor. Installed packs are compared by digest, never by name alone.

## Agora Core compatibility

`supported_core` in the [flavor manifest](../reference/flavor-manifest.md) is the only declaration of compatible Core versions; `pyproject.toml` must carry the same range.

1. A Core minor is added to the range only after `scripts/verify_all.py` and the full test suite pass against that exact version.
2. The lower bound is the oldest Core the suite still passes against; it is raised deliberately, with a changelog entry.
3. A newer Core is not assumed compatible: the manifest check fails with the installed and supported versions, and the range must be widened by a reviewed change.
4. Anything that Core lacks is requested upstream in `Modern-Ash/agora` and consumed here only after a released boundary ([repository boundaries](../repository-boundaries.md)).

Current range: `>=0.8.2,<0.10`, verified against Core 0.8.2 (locked environment) and 0.9.0.

## Releases

1. Every change lands through a pull request that passes `uv run python scripts/verify_all.py`.
2. Update [CHANGELOG.md](../../CHANGELOG.md): move `Unreleased` entries under the new version and date.
3. Bump the version in `pyproject.toml` and the flavor manifest in the same change, then tag `vMAJOR.MINOR.PATCH` on the merged commit.
4. A release states its supported Core range and any contract schema version it introduces or removes. Deprecated names and contracts stay documented for at least one minor release before removal.
5. Releases carry no credentials, provider SDKs or unverified compliance claims.

## Upgrade compatibility

A released Method Pack change must not corrupt work already in flight. `tests/test_upgrade_compatibility.py` exercises this against a real Core workspace:

- a compatible version bump installed over an existing pack (`--force` is required) keeps work in `construction` completable through `completed`, and `agora validate` still passes;
- replacing a pack silently is refused without `--force`;
- an incompatible change (a state renamed while transitions still reference it) is rejected by Core, and the project stays valid and completable.

Registry-distributed upgrades additionally use signed, previewed and recoverable installs (see the [Enterprise profile](../profiles/enterprise.md)). Rollback is a signed forward release, never an edit of accepted history.
