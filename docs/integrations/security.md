# Security finding normalization

The `security-findings` profile turns redacted scanner metadata into provider-neutral findings,
accountable decisions, and Agora Core `security-scan` evidence. Scanners remain external sources;
Agora does not execute scans or claim that different rules and engines are equivalent.

## Finding contract

`agora-ai-sdlc/security-finding/v1` supports `sast`, `dependency`, `secret`, `container`, and `iac`.
Every finding records an immutable id, severity, rule, summary, optional location, scanner name,
scanner finding id, and bounded HTTPS report reference. Scanner name is attribution only and never
changes severity, thresholds, or authority.

Severity is exactly `low`, `medium`, `high`, `critical`, or `unknown`. Unknown scanner severities
must remain `unknown`; guessing a severity is prohibited. Unknown always blocks while open.

The schema rejects raw report bodies and URL credentials, query strings, fragments, and non-HTTPS
references. Core's reviewed GitHub adapter already redacts secret values. Every other adapter or
neutral `security-scanning` wrapper must perform equivalent redaction before normalization. Import
a raw report only through a separately reviewed Core artifact process; this profile stores its
external reference, not its content.

## Thresholds

| Active depth | Open severity that blocks |
| --- | --- |
| minimal | critical, unknown |
| standard | high, critical, unknown |
| comprehensive | medium, high, critical, unknown |
| regulated | low, medium, high, critical, unknown |

These thresholds are monotonic. The minimal depth does not require `security-scan` in its base gate,
but when the profile is evaluated it still blocks critical or unknown open findings. A successful
assessment becomes Core `security-scan` evidence; a blocked assessment becomes failure evidence.
Core remains the lifecycle and gate authority.

## Decisions and authority

Decisions are appended to the normalized finding. They never delete or rewrite its original fields;
an original-content fingerprint detects later mutation.

| Decision | Required authority | Core projection |
| --- | --- | --- |
| resolved | security-reviewer | resolved |
| false-positive | security-reviewer | waived |
| accepted-risk | human governance-owner | waived |

Every decision requires actor, actor kind, role, reason, and bounded evidence reference. An AI actor
cannot accept risk as governance owner. Core 0.8.2 distinguishes `resolved` and `waived`; the flavor
record remains authoritative for the richer accepted-risk versus false-positive meaning. This is a
finding decision, not an independent-review waiver and not a blanket gate waiver.

## Prerequisites, permissions and failure modes

**Prerequisites.** An external scanner (or reviewed `security-scanning` wrapper) that emits redacted metadata, and Agora Core 0.8.2 or later. No scanner account is needed for the offline sample.

**Permissions.** The profile is read-only toward scanners: it never executes scans or holds scanner credentials. Resolving or waiving a finding requires the authority in the table above; an AI actor cannot accept risk. Persisting resulting artifacts and evidence needs an already assigned quality-reviewer.

**Failure modes.**

| Situation | Result |
| --- | --- |
| Unknown or unmapped scanner severity | Recorded as `unknown`; blocks while open |
| Raw report body, URL credentials, query, fragment or non-HTTPS reference | Schema rejection; nothing is stored |
| Decision without actor, role, reason or evidence reference, or by insufficient authority | Rejected; the finding stays open |
| Mutation of an original finding | Detected by the original-content fingerprint |
| Blocked assessment | Recorded as failure evidence, never as success |

## Core mapping

The profile maps category to Core review pass (`security-sast`, `security-dependency`, and so on),
rule to policy, and preserves severity, summary, and location. Core persists open/resolved/waived
history. Scanner identity and report reference remain in the richer flavor finding and registered
evidence artifacts because Core's finding record has no corresponding fields.

In the current AI-SDLC Method Pack, security-reviewer and governance-owner are defined roles but are
not required seats in the base swarm, so Core 0.8.2 cannot add those assignments after swarm
creation. The flavor evaluates decision authority before projection; an already assigned
quality-reviewer may persist the resulting artifacts and evidence. Projects that need Core-enforced
role assignment must use a reviewed Method Pack variant that requires those seats.

Run the offline scenario:

```console
agora-ai-sdlc run-sample security-findings
```

The sample first demonstrates blocking high/critical findings, then applies one resolution, one
human risk acceptance, and one false-positive decision. Low open findings remain visible below the
standard threshold, and all original findings remain queryable in Core.
