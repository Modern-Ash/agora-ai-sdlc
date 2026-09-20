# Starter profile

Starter bootstraps one team and one repository at standard depth. A human Product Owner owns intent and acceptance, and a distinct human Quality Reviewer owns independent verification. Architect, Builder, and Operator execution can remain human or use at most two explicitly declared Agora-supported runtimes (`generic`, `codex`, or `claude`). Runtime declarations configure identity only; the bootstrap does not discover credentials, install CLIs, or launch agents.

## Preview and apply

The configuration file is explicit and credential-free. Preview validates the complete configuration and reports the target, exact `ai-sdlc@0.1.0` Method Pack, actors, assignments, swarm, work item, and write locations. It does not create the target or `AGORA_HOME`.

Interactive use prints that preview and writes only after `y` or `yes`:

```bash
agora-ai-sdlc starter-bootstrap --config starter.json --target /path/to/repo --home /path/to/agora-home
```

Deterministic automation must opt in with `--yes`:

```bash
agora-ai-sdlc starter-bootstrap --config starter.json --target /path/to/repo --home /path/to/agora-home --yes
```

The apply path initializes Git only when absent, preserves existing repository files, creates supported Agora project state, installs the shipped Method Pack snapshot, creates project-local actors, assigns all required roles, and creates the first Unit of Work in `readiness`. Run `agora validate` before beginning work.

## Limits and upgrade

Starter is local and single-team. It does not configure provider credentials, external tools, shared registries, remote policy inheritance, or multi-user Studio. Move to Enterprise for multiple teams and signed registries, Modernization for migration controls, or Regulated for signed actions and stronger segregation.
