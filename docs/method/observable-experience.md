# Observable guided experience

This AI-SDLC presentation slice keeps a human informed without making an LLM
narrate progress, poll a process, or reload the entire guided skill on every turn.
Core is still the authority. A read-only observation is **not** a gate decision,
execution authorization, artifact validation, independent review or completion.

## Commands

Observe one existing Core Work, with no issue-to-bootstrap fallback:

```bash
aisdlc observe --swarm delivery --work issue-8 --lang es
aisdlc observe --swarm delivery --work issue-8 --detail detailed --lang es
```

The Work must actually exist in Core. An Intent named `issue-8` is not sufficient.
If the issue/Work binding is missing, observation reports it; it never substitutes
`first-work`, creates a Work, changes roles or bypasses a gate.

For continuous local observation in another terminal:

```bash
aisdlc observe --swarm delivery --work issue-8 --watch --interval 2 --lang es
```

Watch sleeps locally, has no model or provider calls, and stops on Ctrl-C (exit
130). Use `--duration 60` to stop after a bounded interval. Interval is 1–60 seconds;
duration is at most 86400 seconds. Time spent in a Core read is not preempted.
An unchanged-state heartbeat reports that the **observer** is alive, not that an
executor is running. Session status is the last durable Core observation; agents
launched outside Core are not discovered by this command.

## Two channels, not two names for the same transcript

Human view: title, exact Work/revision, method, state, recorded branch/base, current
gates, blockers, approval roles, sessions and their provenance, activity, artifact
references, usage and the next review step. Normal, detailed and diagnostic views
are deterministic local rendering. Warnings and authority boundaries are always
visible, at every detail level.

Machine view: `--json` returns one `agora-ai-sdlc/observation-summary/v1` object.
It excludes activity, sampling timestamps and heartbeat text. Human language and
`--detail` do not alter it. `--json --watch` is rejected: never create a polling
conversation to keep a human informed.

**stderr is not an isolation boundary.** A host capturing both stdout and stderr
must use a separate human channel and must not reinject that file into the model:

```bash
aisdlc observe --swarm delivery --work issue-8 --json --detail diagnostic \
  --ui-file /tmp/agorix-ui-new.log --lang es
```

Only the compact snapshot goes to stdout. The rich view goes to the separate file;
no UI chatter goes to stderr. `--ui-file` also works with `--watch`, in which case
the observer writes only the human file. The file must be new; it is created with
private permissions and never overwrites/appends to an existing file. Symlinks
and paths inside `.agora` or `.git` are refused. Output is capped at 1 MiB; watch
stops if the channel is full or fails. These are local UI files, not Core evidence.

Start can publish real operation events to that same kind of separate channel:

```bash
aisdlc start --issue 8 --agent opencode --json \
  --ui-file /tmp/agorix-start-new.log --lang es
```

Events identify runtime selection, issue read/reuse, Intent resolution and handoff
preparation. They do not alter the existing Start JSON contract or handoff bytes.
On a human terminal, Start also displays progress automatically. Start still does
not launch an executor: its last event says so. A broken UI sink cannot retroactively
invalidate a completed Core operation; the ordinary command result remains the
source for whether Start succeeded.

## Scope, boundedness and privacy

The observer uses public Core reads (`show_work`, `lifecycle`, `activity`,
`list_sessions`, `artifacts`, `summarize_usage`). It never parses `.agora` lifecycle
files directly and never invokes a runner or a network client. Core can execute
its own local Git checks while evaluating a lifecycle.

The default limit is 20 records per section; `--limit` is 1–50. Truncation is
explicit. If governance is truncated, the next action asks for Core inspection,
not advancement. Output is bounded; current Core APIs can still enumerate larger
record sets before filtering. Reads are best-effort, not an atomic authorization
snapshot. Detected changes to Work state/revision require a fresh inspection.
Even an unchanged display does not authorize a later mutation.

Raw commands, tool outputs, exception bodies, prompts, transcripts, credentials,
keys and signatures are not projected. Activity displays event types and identity
references, not free-form summaries. Metadata is length-limited, common secret
patterns and email addresses are redacted, URLs lose credentials/query/fragment,
and terminal control sequences are removed. This is defense in depth, **not a
complete PII classifier**. Sensitive source metadata must still obey project
classification and least-privilege policy.

## Resource accounting is evidence, not inference

Usage is labelled as work-level recorded usage, with Core's per-dimension
`measured`, `provider-reported` or `unknown` basis. No records means unavailable,
not zero. A recorded zero is shown as zero. Missing recorded consumption means
remaining budget is unknown, even when a configured limit exists. The observer
does not infer costs from model names, bytes, plan duration or subscription fees.
`cost_usd` is null because the consumed Core contract has no normalized currency.
Runtime/model/provider labels retain their provenance basis; configured identity
is not relabelled as an observed provider execution.

Rendering and watching make no model calls and do not append their text to agent
context. They still incur local CPU, I/O and storage costs. A host that explicitly
feeds the UI file to a model will incur context cost; the CLI cannot prevent that
outside its boundary. There is no claim of a measured percentage of token savings.

## Progressive multi-agent skill

```bash
aisdlc skill --phase inception
aisdlc skill --phase review --json
aisdlc skill --phase review --json --content
aisdlc skill --phase construction --paths
```

The root skill retains every always-active authority boundary. Each invocation
loads the root plus **one** requested phase resource, not every phase. Metadata
includes exact byte sizes and SHA-256 digests; token count stays null. `--json`
returns metadata only unless `--content` is explicit. Phase text stays English
and is identical for every executor and human presentation language.

Resources are `inception`, `construction`, `review`, `delivery`, `readiness` and
`governance`. The installer copies the full resource set, preserving unrelated user
files; packaging includes it in the wheel. The Inception handoff identifies the
specific resource needed. Installing a newer Python package alone does not update
a previously copied project skill; use the explicit skill synchronization command
below rather than overwriting project lifecycle state:

```bash
aisdlc skill --install --root .
```

Synchronization updates only the packaged guided skill resources. It does not
change the Method Pack, Work, decisions, artifacts, roles, or approvals.

## Explicit remaining boundaries

This feature does not solve the issue-to-Work binding, enforced governed executor,
first-class human decision persistence, automatic review/repair routing or the
per-iteration branch/PR policy. Those remain separate tracked changes. The skill
explains how to honor those boundaries without pretending its prose implements
missing enforcement. Multi-agent portability never means spawning extra agents
by default.
