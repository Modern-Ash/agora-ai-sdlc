# Project installer

`agora-ai-sdlc install` bootstraps a real Agora AI-SDLC project using an interactive wizard or a reproducible configuration file.

The installer is credential-free. It declares runtimes, providers and models but never asks for API keys, writes secrets, installs provider CLIs or changes provider credentials.

## Interactive

```bash
agora-ai-sdlc install /path/to/project
```

The wizard detects whether the target already contains a Git repository and asks for:

- project id and name;
- adoption profile and governance depth;
- primary programming language;
- optional framework;
- delivery pathway;
- optional GitHub, GitLab, Jira, CI, security and observability integrations;
- zero or more AI runtimes;
- human or AI execution per architect, builder and operator role;
- initial swarm objective and first governed work item.

A runtime contains only:

```yaml
id: primary
integration: claude
provider: anthropic
model: claude-sonnet
```

For Ollama, OpenCode or another runtime without a dedicated Core adapter, use `integration: generic` and declare the provider/model identity explicitly.

## Reproducible config

Generate a config without applying:

```bash
agora-ai-sdlc install /path/to/project --write-config ai-sdlc-install.yaml
```

Apply later:

```bash
agora-ai-sdlc install /path/to/project \
  --config ai-sdlc-install.yaml \
  --home ~/.agora \
  --yes
```

The project receives:

- Agora Core project state under `.agora/`;
- the AI-SDLC Method Pack;
- active flavor/profile/depth metadata;
- actors and role assignments;
- the first Unit of Work;
- `ai-sdlc/project.yaml` containing non-secret project metadata such as language, framework, pathway and enabled integrations.

## Profiles

The installer supports `starter`, `enterprise`, `modernization` and `regulated`. A profile may require a minimum depth. The installer rejects weaker depth selections before writing anything.


## Agora Core dependency and handoff

Installing `agora-ai-sdlc` installs `agora-framework` as a Python dependency. Users should not normally install Core separately.

Before writing project state, `agora-ai-sdlc install` now verifies:
- the installed Agora Core package version;
- compatibility with the flavor's supported Core range;
- availability of the `agora` CLI in the active environment.

A successful installation reports the Core version/executable and the next operational commands:

```bash
agora validate
agora status --board
agora-ai-sdlc continue
```

The installer also copies the portable guided-agent skill to:

```
.agora/skills/agora-ai-sdlc-guided/SKILL.md
```

The default guided command renders a decision card instead of a raw gate failure. It includes:

- objective/work identity and active Method Pack;
- current and target stages;
- gate id and responsible role;
- readiness checks for artifacts, criteria, clarifications, evidence, Git policy and approvals;
- the remaining obligations in human language;
- the explicit boundary between the responsible human and the assisting AI;
- the recommended next interaction.

Additional disclosure modes:

```bash
agora-ai-sdlc continue --commands
agora-ai-sdlc continue --expert
agora-ai-sdlc continue --json
```

`--commands` shows the grouped underlying Core sequence together with a reason for every step. For
the Starter readiness slice this may contain artifact preparation/registration, clarification,
human approval, transition and the final re-read. It is intentionally advisory: commands marked as
human decisions must not be executed by an agent without explicit confirmation.

`--expert` adds the original Core blocker text plus the complete structured decision snapshot for
diagnosis. `--json` returns the same decision as machine-readable data for IDE, TUI or automation
clients without creating a second lifecycle authority.

AI-SDLC owns the bootstrap and guided experience; Agora Core remains the lifecycle authority after bootstrap.
