# GitHub delivery profile

The `github-delivery` profile maps AI-SDLC delivery facts to Agora Core's reviewed GitHub CLI
adapters. Agora remains the lifecycle authority; GitHub remains an external operational source.
The profile does not contain an API client, launch `gh auth`, or persist credentials.

## Contract mapping

| AI-SDLC fact | Core adapter operation | Durable reference |
| --- | --- | --- |
| Unit of Work | `github-issues/view` | Issue number, state, and URL |
| Implementation | `github-pull-requests/view` | Pull Request number, branch, base, state, and URL |
| Independent review | `github-pull-requests/view` | Current `reviewDecision` and Pull Request URL |
| Verification | `github-actions/view-run` plus PR check rollup | Run ID, URL, status, conclusion, and full commit SHA |

Verification passes only when the Actions run URL appears in the Pull Request's current check
rollup, its branch matches the Pull Request head, its full `headSha` equals the expected revision,
and both the rollup and run are successful. A successful check for an older commit fails closed.
GitHub review and Agora lifecycle approval remain separate facts.

## Permissions

`read-only` is the default mode. Applying it installs only Core's reviewed `github-issues`,
`github-pull-requests`, and `github-actions` adapters and grants the minimum read capabilities to the
AI-SDLC roles that observe each fact. It does not grant `issue.write`, `issue.transition`,
`review.write`, `review.decide`, `review.merge`, or `ci.run`.

`delivery-write` permits routine collaboration capabilities in policy, but every operation still
requires both an explicit project-local Core capability grant and confirmation. `merge-write` keeps
`review.merge` separate. Core rechecks capability, signed actor authority when configured, work and
environment policy, and the unchanged prepared command at launch time. Authentication in `gh`
never grants Agora authority.

## Synchronization

Reads are explicit snapshots, not a background mirror. Each normalized observation has a canonical
fingerprint; ingesting the same observation again is a no-op. A changed external fact creates a new
observation. Provider execution failures and malformed provider facts raise provider errors;
profile denials return structured policy blockers.

A closed GitHub Issue does not complete Agora work. A reopened Issue is recorded as a new external
observation; Core's tracker reconciliation may reopen terminal local work as a new immutable
revision when separately bound and authorized. The profile never closes, reopens, or transitions
Agora work implicitly.

External IDs remain identifiers and HTTPS URLs remain evidence references. Provider response
bodies are normalized before persistence; credentials and tokens are never evidence.

## Offline and live use

Run the complete credential-free walkthrough:

```console
agora-ai-sdlc run-sample github-delivery
```

For an opt-in live read, install and authenticate `gh` outside Agora, apply the read-only profile to
the project, and use Core's `agora tool sync` with a new run ID for each Issue, Pull Request, and
Actions observation. Use a non-production or explicitly approved repository. Do not enable a write
mode for a read smoke test, and do not commit Tool Run results containing private repository data.

The executable and minimum version come from Agora Core's adapter contracts. See the installed
Core GitHub ecosystem guide for exact `tool sync` inputs and runtime troubleshooting.
