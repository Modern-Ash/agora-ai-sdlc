# Data Handling Policy

Issue #23 defines governance metadata for deciding whether referenced inputs may be sent to a runtime before launch. Agora Core remains the lifecycle authority; callers run this deterministic check before invoking a runtime and before recording resulting evidence in Core.

## Classifications

From least to most restrictive: `public`, `internal`, `confidential`, `restricted`. The effective classification is the highest classification among all referenced inputs. Unknown classification is denied by default; a policy may explicitly substitute one of the four classifications instead.

## Runtime Eligibility

An eligibility declaration names the runtime, its maximum classification, permitted execution boundaries, a revision and supporting evidence. Boundaries are `local`, `customer-controlled` and `external`. Runtime identity and the actual boundary must meet the configured provenance trust level and match the eligibility declaration. Missing identity, boundary or evidence fails before launch.

Launch authorization binds the runtime, boundary, effective classification, eligibility revision and every input id, revision and classification. Changing any of them makes prior authorization stale. The fingerprint is a deterministic change detector, not a signature or security token.

Policy failures return only offending input identifiers. Input content is outside this contract and is never accepted, inspected or included in output.

## Responsibility And Limits

This policy is not a DLP product and does not discover, inspect, redact or prevent copying content. Customers remain responsible for assigning accurate classifications, defining runtime eligibility, securing evidence, and enforcing actual network, process, container, host and operating-system isolation. A `local` or `customer-controlled` declaration is metadata, not proof that the infrastructure is isolated.

The deterministic reference implementation is `agora_ai_sdlc.data_classification`. It has no network, provider SDK or credential dependency.
