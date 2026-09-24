# templates

Schema-versioned artifact templates (`agora-ai-sdlc/artifact/v1`). Field semantics and traceability rules: [docs/method/artifacts.md](../docs/method/artifacts.md). Shipped in the wheel.

Modernization templates extend the shared artifact chain without adding lifecycle states. See the [Modernization profile](../docs/profiles/modernization.md).

Level 1 / Level-N planning uses [plan.md](plan.md) with additional deterministic validation documented in [planning](../docs/method/planning.md).

Cross-repository analysis uses [impact-analysis.md](impact-analysis.md), with provider-neutral repository and contract semantics documented in [impact analysis](../docs/method/impact-analysis.md).

Governed enterprise changes use [change-request.md](change-request.md), [change-plan.md](change-plan.md), and [configuration-delta.md](configuration-delta.md). See [change management](../docs/method/change-management.md).

AI-SDLC compatibility adds first-class templates for User Stories, NFRs, Risk Register, Measurement Criteria, optional PRFAQ, Logical Design and Deployment Unit. These preserve the paper's method vocabulary without coupling templates to a specific LLM or cloud provider.
