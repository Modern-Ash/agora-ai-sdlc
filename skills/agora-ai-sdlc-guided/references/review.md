# Review — independent, bounded, revision-aware

Start with `aisdlc execution-bundle --root . --swarm <swarm> --work <work> --json`. Treat its exact branch/base/HEAD, changed and dirty paths, acceptance criteria, candidate verification commands and mechanical risk flags as deterministic review facts. Do not spend model tokens rediscovering those facts. Then consume `aisdlc verify --root . --swarm <swarm> --work <work> --json` (or a previously authorized `--run` report) as mechanical verification evidence. The reviewer should concentrate on semantic correctness, architectural consequences and findings that Python/static tooling cannot determine.

Review the Task, exact diff/revision, relevant decisions, acceptance criteria and
verification evidence. Use a distinct reviewer session from the producer; use a
different runtime/provider only when required or configured. Record the actual
separation observed; do not infer provider independence from model names.
If independent execution is unavailable, disclose it instead of self-certifying.

Produce findings with stable IDs, evidence/location, severity, affected decision
or invariant, and whether correction is determined by an existing authorization.
Severity alone does not grant repair authority. A minor finding can require a
human product decision; a serious defect can have a mechanically determined fix.

A host that supports producer/reviewer delegation may route authorized repairs
and rechecks without manual prompt transport. Honor its iteration/time/token
budget. When it cannot converge, present one concise decision with alternatives.
Do not claim that the skill itself implements a runner or an enforced repair loop.

Focused review checks the changed findings AND global invariants affected by the
diff. Never pass contradictory requirements merely because each requested phrase
is present. Numeric layout constraints need feasible boundaries; check degraded
or constrained cases, not just the presence of a number.

Keep original review history and append the subsequent dispositions against the
actual artifact revision/hash. Do not reuse a prior PASS for changed content
without stating the scope rechecked. Raw model reasoning is not review evidence.
No product edits, approval changes or merge from the reviewer role without
separate authority.
