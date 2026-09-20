# AI-SDLC self-test

`agora-ai-sdlc self-test` verifies the installed distribution without requiring an initialized project, network service, provider account, or credential.

```console
agora-ai-sdlc self-test
agora-ai-sdlc self-test --json
```

The harness discovers packaged assets at runtime. It validates the flavor manifest and Core compatibility; parses every profile, policy, and JSON contract; inventories templates; executes every sample; and drives the AI-SDLC Method Pack to completion through Agora Core. The role case uses human and AI holders, represented-swarm delegation for compatible roles, and confirms that unsupported service holders fail closed.

Each operation runs under a temporary harness workspace, while executable samples create their own temporary Git repositories. Success removes the harness workspace. An interruption also cleans it before propagating the interrupt. Failure returns exit code `1`, retains the harness workspace, and reports its path.

With `--json`, stdout is exactly one result conforming to `agora-ai-sdlc/self-test-result/v1`; progress remains on stderr. The checked-in schema is [`contracts/conformance/self-test-result-v1.schema.json`](../../contracts/conformance/self-test-result-v1.schema.json).

Passing the self-test establishes offline package and lifecycle conformance only. It does not call or certify live models, provider adapters, external CI, cloud services, or production environments.
