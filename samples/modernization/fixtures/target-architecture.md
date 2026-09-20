---
schema: agora-ai-sdlc/artifact/v1
kind: target-architecture
version: 1
id: TAR-001
work: feature
revision: 1
traces-to: [DPM-001, CHR-001]
separation-policy: [distinct-actor]
required-sections: [Target context, Components and interfaces, Data evolution, Transition constraints, Decisions and risks]
---
# Target architecture
## Target context
Replace checkout calculation behind the existing interface.
## Components and interfaces
The input and output contracts remain neutral JSON documents.
## Data evolution
No persistent data moves in this slice.
## Transition constraints
Old and new calculators can run side by side.
## Decisions and risks
Unknown empty-cart behavior requires accountable acceptance.

