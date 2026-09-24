# Positioning

| Audience | Value | Boundary |
|---|---|---|
| Engineering teams adopting AI agents | A governed lifecycle with gates, evidence and independent review | Runs on Agora Core; no hosted service required |
| Enterprises | Profiles for signed registries, segregation and provenance | Regulated controls are evidence-backed metadata, not certification |
| Services buyers | Assessment, pilot and adoption [packages](../commercial/README.md) | Cloud mappings are illustrative, not endorsements |

## Relationship to AWS AI-DLC

AWS AI-DLC is methodological inspiration only. This project is independent, not affiliated with or endorsed by AWS, and requires no AWS service. The [concept mapping](../reference/aws-ai-dlc-mapping.md) lists what is shared at the level of public terminology.

## Differentiators

Agora AI-SDLC does not require teams to practice the method by copying a prompt library. It turns the
method into an executable, observable developer experience:

- **Continuous Agora Flow wizard.** One session leads the practitioner through Inception, Construction
  and Operations, asks only material clarification questions, proposes one next action, and explains
  what confirmation will do.
- **Method learning in the workflow.** AI-DLC vocabulary and the reason for the current step are shown
  inline, reducing training overhead without renaming the method.
- **Executable governance.** Human validation, gates, evidence, roles and authority are durable Core
  facts rather than instructions that exist only in prompts.
- **Progressive Intelligence.** Deterministic/Core logic is preferred first, then local Laya System-1,
  then local/free generative execution, then external/frontier execution when needed.
- **Context Economy.** Candidate context is bounded deterministically, semantically pruned fail-open,
  measured before/after and persisted so the executor uses the same context the user saw.
- **Provider neutrality.** The lifecycle and artifacts do not depend on AWS services or one LLM/IDE.
  Compatibility profiles map the method to environments without changing its canonical meaning.
- **Brownfield semantic elevation.** Existing code is modeled before change, keeping the context
  concise and reviewable instead of giving an agent an unconstrained repository dump.

Provider-neutral naming ([ADR-0003](../decisions/ADR-0003-provider-neutral-naming.md)), the separate
flavor boundary ([ADR-0001](../decisions/ADR-0001-separate-flavor-repository.md)), and Core-enforced
authority remain architectural foundations.

See [AI-DLC method compatibility](../method/ai-dlc-compatibility.md) and the
[Agora Flow wizard](../method/agora-flow-wizard.md).
