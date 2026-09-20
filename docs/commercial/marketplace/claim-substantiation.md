# Claim substantiation register

Every material claim marker used in [listing copy](listing.md) must have exactly one row here. Evidence establishes only the permitted wording and boundary; it must not be expanded into guarantees, cloud endorsement, certification, or capabilities not shipped by the current release.

| ID | Permitted claim | Classification | Evidence | Boundary |
| --- | --- | --- | --- | --- |
| C01 | Agora AI-SDLC is provider-neutral and runtimes, providers, and deployment infrastructure are replaceable | Implemented architecture constraint | [Agent contract](../../../AGENTS.md), [reference architecture](../reference-architecture.md) | No claim that every provider has a bundled adapter or has been live-tested |
| C02 | Four bounded service packages cover assessment, Starter pilot, Enterprise adoption, and legacy modernization | Published service definition | [Package overview](../README.md) and the four linked package contracts | Scope, schedule, goals, and acceptance require a customer statement of work; no outcome guarantee |
| C03 | Agora Core owns lifecycle state, gates, approvals, and durable evidence while the flavor supplies AI-SDLC assets and validation | Implemented product boundary | [Architecture](../../architecture.md), [repository boundaries](../../repository-boundaries.md), [new-product sample](../../../samples/new-product/README.md) | External systems remain authoritative for their facts; flavor validation is not infrastructure proof |
| C04 | The installed distribution has a self-test and credential-free executable samples | Implemented and tested capability | [Self-test reference](../../reference/self-test.md), [sample inventory](../../../samples/README.md) | Offline conformance only; no customer environment, cloud, runtime, or production certification |
| C05 | Enterprise supports signed project-local registry preview and transactional update with signed-forward recovery | Implemented and tested capability | [Enterprise profile](../../profiles/enterprise.md), [Enterprise sample](../../../samples/enterprise/README.md) | No hosted registry, fleet transaction, Control Plane, key custody, or cross-project rollback |
| C06 | Professional Services may be scoped in a customer-selected AWS environment while Agora itself remains cloud-neutral | Consulting delivery boundary | [Optional deployment mappings](../reference-architecture.md), [shared responsibility](../security-and-responsibility.md) | Does not establish Marketplace eligibility, AWS sponsorship, a bundled AWS adapter, or tested production architecture |
| C07 | Repository software is Apache-2.0 and separate from paid services | License and service boundary | [Apache License](../../../LICENSE), [package overview](../README.md) | License does not include consulting, customer-specific implementation, operations, or support |
| C08 | Customers retain deployment responsibility for identity, credentials, isolation, residency, provider terms, backups, and incidents | Published responsibility boundary | [Security and shared responsibility](../security-and-responsibility.md) | A profile check is not certification or proof that customer controls operate effectively |
| C09 | This draft sells Professional Services and bounded engagement support, not SaaS or ongoing managed operations | Offer boundary | [Package overview](../README.md), [service exclusions](../enterprise-adoption.md) | Any managed service, premium support, SLA, or 24x7 obligation requires separate capability and approval |

## Claim review rules

- A new marker in buyer-facing copy requires a new row with local, reviewable evidence before merge.
- A changed claim requires re-reading every linked source and narrowing the wording when evidence is partial.
- Roadmap items may be named only as unavailable future scope, never as a buyer-facing available capability.
- Customer examples, percentages, benchmarks, testimonials, partner status, certifications, awards, and savings claims require separate evidence not present in this repository.
- The submission reviewer must confirm that each source still reflects the released version and that no marker is removed from public copy while leaving its assertion behind.
