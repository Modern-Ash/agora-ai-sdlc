# Regulated profile

Runs a credential-free Regulated delivery in a throwaway Git repository. Every actor holds an in-memory
Ed25519 key that exists only for the run; Agora Core verifies each signature.

```bash
uv run agora-ai-sdlc run-sample regulated
```

The sample shows an unsigned critical mutation rejected, a non-human product owner and a
builder/quality-reviewer combination rejected before assignment, incomplete (declared) model provenance
blocked while observed provenance is allowed, an unauthorized exception rejected and an authorized
time-bound one recorded, evidence retention metadata bound to signed evidence, and then a full
`readiness -> completed` lifecycle where every critical action is prepared, signed and applied through
Core. It finishes with `agora validate`.

Retention, exception and segregation rules are enforced here as metadata and pre-assignment checks;
legal retention, key custody and organizational audit remain deployment responsibilities (see
[the Regulated profile](../../docs/profiles/regulated.md)).
