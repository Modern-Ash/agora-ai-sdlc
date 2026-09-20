# AI-SDLC tool restrictions

- Roles reference provider-neutral capabilities only (repository, docs, review); no vendor tool is implied.
- The Builder may use repository and CI tools the project permits.
- Deploy, release or infrastructure changes need an explicit project environment grant held by the Operator; never implied by another role.
- Intent and unit-of-work changes require the Product Owner or the Architect.
- Exceptional paths need an explicit transition and gate, not a flag.
