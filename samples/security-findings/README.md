# Security finding profile sample

This offline sample normalizes SAST, dependency, secret, container, and IaC findings from arbitrary
scanner names. High and critical open findings first block the standard profile. Accountable
resolved, accepted-risk, and false-positive decisions are then added without deleting the original
finding, allowing only the remaining low findings below the standard threshold.

The sample projects records into Agora Core review findings, registers external references, emits
successful `security-scan` evidence, and completes the AI-SDLC lifecycle without a scanner, network,
credentials, raw report, or secret value.

```console
agora-ai-sdlc run-sample security-findings
```
