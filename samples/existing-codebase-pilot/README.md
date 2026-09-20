# Existing-codebase multi-LLM pilot

This credential-free pilot copies a maintained catalog service into a temporary Git repository and executes an explicit volume-pricing change through real Agora Core lifecycle and session APIs.

The first fake producer implements only the happy path. A fake reviewer on another provider requests changes, and the construction gate remains blocked. The same producer actor is then moved to a replacement provider, corrects the behavior, receives an independent approval, records current-commit CI evidence, and completes the lifecycle. No network, provider CLI, LLM, credential, or production service is used.

```console
agora-ai-sdlc run-sample existing-codebase-pilot
```

See [the pilot guide](../../docs/pilots/existing-codebase.md) for evidence boundaries and the optional live procedure.
