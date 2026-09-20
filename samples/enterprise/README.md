# Enterprise signed registry

Runs an offline, credential-free project-scoped install and upgrade from an ephemeral Ed25519-signed organization registry. The private key exists only in process memory; the temporary distribution contains only its public key and is deleted after success.

```bash
uv run agora-ai-sdlc run-sample enterprise
```

The sample previews both operations, records Core provenance and update history, and reports the signed-forward rollback strategy.

