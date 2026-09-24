# Agora AI-SDLC

Vendor-neutral AI-first software-delivery distribution built on [Agora Core](https://github.com/Modern-Ash/agora). Agent contract: [AGENTS.md](AGENTS.md). Scope: [docs/product-scope.md](docs/product-scope.md).

## Install a project

Bootstrap a real project interactively. `aisdlc` is the short alias for `agora-ai-sdlc`:

```bash
aisdlc install /path/to/project
# equivalent: agora-ai-sdlc install /path/to/project
```

Or use a reproducible, credential-free configuration:

```bash
agora-ai-sdlc install /path/to/project --config ai-sdlc-install.yaml --yes
```

The installer selects adoption profile, governance depth, language/framework, optional integrations, AI runtimes and human/AI role execution. See [Project installer](docs/installer.md).

Start a new governed delivery from the existing entry point; on an interactive terminal it flows directly into the same wizard:

```bash
aisdlc start --issue 26
```

For an already-started Work, resume the same continuous wizard:

```bash
aisdlc continue
```

On a real terminal, the wizard proposes the next AI-DLC step, asks only material clarification questions, explains what it knows and what it will do, and accepts Enter as the happy-path confirmation. Runtime/model selection appears only when execution actually needs it. In non-TTY contexts it falls back to one-shot structured output.

It renders a decision card with objective, method, current/next stage, responsible role, gate readiness,
satisfied/missing obligations, the human/AI responsibility boundary, and the recommended next action.
The selected agent follows the portable skill under `.agora/skills/agora-ai-sdlc-guided/SKILL.md`.

Use the disclosure modes when needed:

```bash
agora-ai-sdlc continue --commands  # show the grouped Core command bundle and why each step exists
agora-ai-sdlc continue --expert    # add raw Core blockers and the structured decision snapshot
agora-ai-sdlc continue --json      # machine-readable decision for IDE/TUI/automation clients
agora-ai-sdlc continue --non-interactive  # force one-shot output on a terminal
```

The default view deliberately avoids raw `missing-artifacts=[...]` style output. The command bundle is
advisory: human approvals still require explicit confirmation, and every mutation remains an Agora Core
operation. Agora Core remains the lifecycle authority.

## Three interaction surfaces

Agora AI-SDLC exposes the same governed Work through three complementary surfaces. They share the
same Agora Core state, artifacts, evidence, gates and authority model; only the amount of orchestration
changes.

### 1. Agora Flow — automagic adoption mode

For practitioners who should practice AI-DLC without memorizing CLI commands:

```bash
aisdlc start --issue 26   # first entry
aisdlc                    # resume later
```

After `start`, the interactive session remains inside the continuous wizard. Each workflow node explains
the current state and proposes the next action; Enter confirms it. Verification, explicit approvals and
Core-authorized transitions can be executed from that same session. The UI does not instruct the user
to exit and run another `aisdlc ...` command.

### 2. Expert CLI

Experienced users keep the complete command surface and may compose operations directly:

```bash
aisdlc continue --expert
aisdlc context ...
aisdlc execution-bundle ...
aisdlc verify ...
aisdlc decision ...
agora work transition ...
agora approval add ...
```

Flow is therefore an adoption layer, not a restriction or replacement for Agora Core/AI-SDLC commands.

### 3. Automation / machine surface

CI, IDEs and agents can consume the same state non-interactively through JSON and the underlying
Core APIs. Human-friendly Flow decisions never create a separate shadow workflow.

## Local decision plane (Laya)

AI-SDLC can use the free, Apache-2.0 [Laya](https://github.com/NandhaKishorM/laya)
runtime as its only System-1 decision engine before escalating work to a generative model. Laya is advisory only;
Agora Core remains authoritative for lifecycle state, evidence, approvals and transitions.

```bash
# lightweight Core/wizard
pip install agora-ai-sdlc

# full local Decision Plane (recommended for token/context savings)
pip install "agora-ai-sdlc[full]"
```

The normal delivery workflow remains `aisdlc start ...` / `aisdlc continue`; users do not invoke Laya directly. If Laya is unavailable, the wizard fails open to deterministic/generative behavior rather than blocking delivery.

The Context Graph stays deterministic: Laya can prune candidates but cannot introduce unrelated
artifacts. Low-confidence decisions fail open and remain on the normal generative/human escalation
path. See [Local Decision Plane with Laya](docs/decision-plane-laya.md).

See [AI-DLC method compatibility](docs/method/ai-dlc-compatibility.md) for the canonical method mapping and the explicit Agora extensions.

## Continuous delivery wizard

The normal user experience is a single continuous wizard:

```bash
aisdlc continue
```

Agora shows the current delivery step, the facts it is using, open gaps, evidence, the proposed next
action and exactly what will happen after confirmation. Material ambiguities are asked inline and the
answers are persisted as explicit Work context, so agents do not ask the same question again. The
happy path uses `Enter` to confirm, `A` to adjust, `D` for full governance/details and `X` to stop.
No prompt text or second command is required for the normal workflow.

## Detect local AI runtimes

AI-SDLC can inspect the active `PATH` without reading credential files:

```bash
aisdlc runtimes
aisdlc runtimes --json
aisdlc doctor
```

Discovery currently recognizes Codex, Claude Code, OpenCode and Ollama. It distinguishes executable
installation, a responsive version probe, project configuration, and (for Ollama) local service
responsiveness. Detection never implies authentication and never enables a runtime automatically.

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
The [modernization pilot report](docs/pilots/modernization.md) records its baseline, outcome, evidence and limitations. The [Modernization profile](docs/profiles/modernization.md) keeps legacy unknowns explicit and gates incremental slices on traced conversion, equivalence, cutover, rollback and stabilization evidence.
The [Regulated profile](docs/profiles/regulated.md) composes Core signed actions with human accountability, role segregation, observed runtime provenance, and auditable exception and retention metadata without claiming regulatory certification.
The [Studio projection contract](docs/integrations/studio-projection.md) defines the path-free, versioned read boundary for AI-SDLC dashboards; implementation remains in Agora Core and Agora Studio.
The [security and offline resilience suite](docs/reference/security-resilience.md) runs all packaged conformance paths with network connections denied, scans an inert secret canary, distinguishes runtime failures, and injects registry failures.

## Professional Services

The [Professional Services packages](docs/commercial/README.md) define bounded assessment, Starter pilot, Enterprise adoption, and legacy modernization engagements. They separate Apache-2.0 software from paid consulting and tie technical claims to the current release manifest.
