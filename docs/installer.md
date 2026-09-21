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
