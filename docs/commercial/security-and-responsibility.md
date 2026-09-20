# Security and shared responsibility

This model identifies who enforces, validates, supplies, and operates each control in a self-managed Agora AI-SDLC deployment. It applies to the repository software and the [reference architecture](reference-architecture.md); a statement of work may assign consulting activities but cannot turn a documented validation into an infrastructure control.

## Control language

- **Agora enforcement** means Agora Core blocks or records an operation according to an installed contract over the state and evidence it can observe.
- **Flavor validation** means deterministic AI-SDLC code rejects nonconforming configuration, metadata, or normalized input before or around a Core operation.
- **Deployment evidence** means a customer-controlled runtime, adapter, person, or external system supplies a bounded fact. Agora can validate its shape and consistency but does not thereby prove the source system or infrastructure.
- **Deployment responsibility** means the customer or its contracted provider operates and assures the real identity, secret, host, network, storage, legal, or incident control.

Passing `agora validate`, a profile check, or an offline sample demonstrates only the evaluated repository contract. It is not certification, legal advice, an audit opinion, or proof of effective production controls.

## Shared-responsibility matrix

| Control | Agora enforcement or flavor validation | Customer deployment responsibility | External provider or Modern Ash role |
| --- | --- | --- | --- |
| Lifecycle, gates, approvals, and rework | Core owns lifecycle mutation and fails closed when its required evidence, approval, or clarification state is missing | Protect repository writes, assign accountable roles, review changes, and prevent bypass through access and branch controls | Modern Ash may configure and test shipped behavior under a statement of work; it does not approve customer work |
| Human and actor identity | Core records configured actors and, where used, verifies current Core signing keys and signatures; regulated checks validate role separation | Prove real identity, joiner/mover/leaver lifecycle, authentication, authorization, key issuance, revocation, and account recovery | Identity and signing-service providers operate under customer contracts; Agora is not an identity provider |
| Credentials and private keys | Flavor schemas reject credential-like fields in governed configuration and evidence; public trust keys may be registered | Generate, store, scope, rotate, revoke, monitor, and recover credentials and private keys; keep them out of Git, logs, prompts, fixtures, and evidence metadata | Secret managers, HSMs, runtimes, and tool providers protect their services under customer-selected terms; Modern Ash does not take custody by default |
| Runtime and model selection | Flavor policies evaluate configured eligibility, classification, budget, fallback, provenance, and reviewer separation using available facts | Configure and constrain actual runtime execution, egress, tool permissions, tenancy, input classification, and trustworthy observations | Runtime/model providers supply service controls and terms; model names never establish identity or independence |
| Infrastructure isolation | Data-handling policy checks declared execution boundary and eligibility but does not inspect hosts or networks | Enforce process, container, host, tenant, network, filesystem, and environment isolation and verify that declarations are true | Infrastructure providers operate their platform boundary; Modern Ash can assess configuration only when scoped |
| Data residency, privacy, and retention | Flavor validates bounded references and configured retention/exception metadata; it does not route content or enforce geography, legal hold, deletion, or WORM storage | Classify data, choose regions and subprocessors, define lawful handling and retention, preserve/delete evidence, and verify all runtime/tool transfers | Providers state locations and processing terms; customer legal/privacy owners decide suitability |
| Provider and model terms | Provenance records provider/model observations and refuses to infer a provider from a model name | Accept licensing, acceptable-use, training, intellectual-property, privacy, export, and commercial terms and track changes | Providers own their terms; Modern Ash does not warrant third-party models or services |
| External delivery, CI, scanner, and telemetry facts | Integrations validate bounded schemas, freshness, revisions, environments, redaction, and references; Core records resulting evidence | Operate sources and adapters, secure API access, ensure factual accuracy, retain raw records externally, and investigate collection gaps | External systems remain authoritative for their facts; Modern Ash may implement a reviewed wrapper when contracted |
| Signed registry and supply | Core verifies configured public trust, signature threshold, checksum, safe extraction, and transactional project placement | Protect publishing and private signing keys, review releases, distribute trust roots, inventory versions, and operate rollout/revocation | Artifact-hosting and key-management providers secure their boundary; Modern Ash may package approved assets but does not host a registry here |
| Backups and recovery | Core preserves transactional project state during supported registry apply failures; it provides no hosted backup service | Define RPO/RTO, back up repositories and external evidence, protect copies, test restoration, and reconcile restored state | Hosting/backup providers meet customer-selected service terms; recovery assistance requires explicit service scope |
| Monitoring and incident response | Agora records governed evidence and follow-up work but does not monitor production, page responders, contain incidents, or execute rollback | Detect, triage, contain, communicate, preserve evidence, rotate secrets, recover systems, perform required notifications, and close corrective work | Customer is accountable; providers meet their incident obligations; Modern Ash is consulted or engaged only when contractually assigned |
| Compliance and assurance | Regulated and other profiles add technical validation and metadata; no profile certifies a system or organization | Map controls to obligations, obtain legal advice, manage risk acceptance, test effectiveness, and commission independent audits or attestations | Qualified legal, compliance, and audit parties provide external assurance; Modern Ash makes no certification claim |

## Data and secret boundary

Agora project state should contain reviewed artifacts, normalized metadata, fingerprints, bounded HTTPS references, approvals, and lifecycle records. It should not contain provider tokens, authorization headers, private keys, raw scanner reports, unrestricted logs, prompts with sensitive content, model reasoning, or credential-bearing URLs.

The customer defines classifications and allowed execution boundaries before runtime launch. The [data-handling policy](../policies/data-handling.md) validates those declarations but is not data-loss prevention. The [model-provenance policy](../policies/model-provenance.md) records observed, declared, or unavailable provenance but cannot create observations that a runtime adapter does not supply. The [security-finding profile](../integrations/security.md) requires redacted normalized findings while scanners retain authority over raw reports.

## Responsibility by deployment pattern

| Pattern | Additional customer controls |
| --- | --- |
| Developer workstation | Device identity, local account and disk protection, process/tool permissions, network egress, credential injection, local backup, and review before push |
| CI automation | Runner isolation and lifecycle, pinned dependencies, least-privilege job identity, secret masking, protected workflows, artifact retention, concurrency behavior, and immutable logs where required |
| Self-managed enterprise | Signing-key ceremonies, immutable release publishing, trust-root distribution, project inventory, rollout waves, drift detection, partial-failure handling, revocation, and signed-forward recovery |

Studio does not reduce these duties. Its browser boundary must use opaque project selection and sanitized projections; access to the loopback host, workstation, and any remote transport remains a deployment concern. The future Control Plane cannot be assigned a present responsibility because it is not part of the current product.

## Incident and recovery model

The customer names an incident owner before production use and integrates repository, runtime, provider, CI, registry, and monitoring events into its response process. At minimum:

1. Stop affected automation and preserve secret-safe evidence when an identity, credential, signer, runtime, integration, or record may be compromised.
2. Revoke or rotate affected credentials and signing keys through the owning systems; update project public trust deliberately.
3. Determine affected repositories, work items, releases, evidence, and external actions. An Agora record is not proof that an external action was harmless.
4. Restore repositories and external records from tested customer backups. Run validation and reconcile revision-specific evidence before resuming transitions.
5. For registry content, publish and review a higher-version signed forward release. Do not edit generated provenance or force an unsupported downgrade.
6. Record corrective work through normal lifecycle gates and satisfy any legal, contractual, customer, or provider notification duties outside Agora.

If an external source is unavailable, required evidence remains unavailable; if Studio is unavailable, Core and CLI remain authoritative and usable; if an enterprise rollout is partial, each project's installed checksum and failure remain independent. These are fail-closed or degraded-presentation states, not permission to fabricate evidence or edit `.agora` directly.

## Service boundary

Modern Ash's [Professional Services packages](README.md) can include assessment, customer-specific configuration, integration, rollout planning, recovery exercises, documentation, and training when stated in a signed scope. Unless explicitly contracted and technically available, Modern Ash does not operate customer infrastructure, hold credentials or private keys, accept risk, provide 24x7 response, guarantee recovery, certify compliance, or become accountable for provider obligations.

The customer remains accountable for accepting the architecture, assigning control owners, approving exceptions and risk, validating provider contracts, and operating the deployment. Third-party providers remain accountable only under their own agreements with the customer.
