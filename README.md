# Agora AI-SDLC

Vendor-neutral AI-first software-delivery distribution built on [Agora Core](https://github.com/Modern-Ash/agora). Agent contract: [AGENTS.md](AGENTS.md). Scope: [docs/product-scope.md](docs/product-scope.md).

## Clone

```bash
git clone https://github.com/Modern-Ash/agora-ai-sdlc.git
# or, with GitHub CLI
gh repo clone Modern-Ash/agora-ai-sdlc
```

## Migration note

This repository was previously named with a trailing dot (`agora-ai-sdlc.`). GitHub redirects the old URL; update any remotes with `git remote set-url origin https://github.com/Modern-Ash/agora-ai-sdlc.git`. This note may be removed after the first published package.

## Development

```bash
uv sync
uv run python scripts/verify_all.py   # full verification
uv run pytest
uv run agora-ai-sdlc --version
uv run agora-ai-sdlc self-test --json
uv build
```

## Executable samples

```bash
uv run agora-ai-sdlc run-sample new-product
uv run agora-ai-sdlc run-sample github-delivery
uv run agora-ai-sdlc run-sample ci-evidence
uv run agora-ai-sdlc run-sample security-findings
uv run agora-ai-sdlc run-sample gitlab-delivery
uv run agora-ai-sdlc run-sample jira-work-items
uv run agora-ai-sdlc run-sample operational-evidence
uv run agora-ai-sdlc run-sample starter
uv run agora-ai-sdlc run-sample enterprise
uv run agora-ai-sdlc run-sample modernization
```

The [GitHub delivery profile](docs/integrations/github.md) is read-only by default and uses Agora
Core's reviewed CLI Tool Packs without requiring credentials for its offline sample.
The [generic CI/CD evidence profile](docs/integrations/ci.md) applies the same commit-bound gate
semantics to GitHub Actions, GitLab CI, Jenkins, or another reviewed neutral adapter.
The [security finding profile](docs/integrations/security.md) normalizes scanner metadata and applies
depth-aware blocking with explicit resolution, false-positive, and human risk-acceptance authority.
The [GitLab and Jira profiles](docs/integrations/gitlab-jira.md) reuse the same neutral capabilities,
keep writes opt-in, and reconcile external facts without changing Agora lifecycle meaning.
The [operational-evidence profile](docs/integrations/observability.md) maps optional monitoring sources to fresh release evidence and deterministic Core control bands without production mutation.
The [Starter profile](docs/profiles/starter.md) previews and bootstraps a one-team repository with explicit human accountability and at most two declared AI runtimes.
The [Enterprise profile](docs/profiles/enterprise.md) validates inherited organization policy and consumes signed registries as project-local snapshots with Core provenance and transactional updates.
The [Modernization profile](docs/profiles/modernization.md) keeps legacy unknowns explicit and gates incremental slices on traced conversion, equivalence, cutover, rollback and stabilization evidence.
The [Regulated profile](docs/profiles/regulated.md) composes Core signed actions with human accountability, role segregation, observed runtime provenance, and auditable exception and retention metadata without claiming regulatory certification.
The [Studio projection contract](docs/integrations/studio-projection.md) defines the path-free, versioned read boundary for AI-SDLC dashboards; implementation remains in Agora Core and Agora Studio.
