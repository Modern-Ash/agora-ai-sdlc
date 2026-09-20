# GitLab and Jira follow-on profiles

The GitLab and Jira profiles reuse the provider-neutral `issue.*`, `review.*`, and `ci.*` capabilities established by the GitHub delivery profile. Provider field names are translated at the profile boundary; Method Pack gates and lifecycle transitions never branch on provider.

## Authority and reconciliation

- GitLab is authoritative for GitLab issue, merge-request, approval, and pipeline facts.
- Jira is authoritative for Jira work-item status and transition facts.
- Agora Core is authoritative for AI-SDLC lifecycle state, gates, approvals, and durable evidence.
- An external status never transitions Agora work. It is an observation that may support a separately authorized Agora transition.
- Normalized observations are immutable. The collector supplies neutral `observed_at` metadata separately from the bounded provider response. An identical fingerprint is an idempotent retry; a changed observation at a new capture time is appended. Different content claiming the same provider, scope, external id, and capture time is rejected as a reconciliation conflict.

Only bounded HTTPS references are retained. Input URLs containing credentials, queries, or fragments are rejected, GitLab paths must exactly match the declared project scope, and Jira keys must match the bounded work-item key grammar before a browser URL is constructed. Raw provider responses are not durable evidence. The GitLab normalizer adds its own commit fragment to the validated pipeline URL so verification stays revision-bound.

## Shared work-item outcome

Both profiles emit `agora-ai-sdlc/work-item-fact/v1`. Provider identity, scope, external id, external state, observation time, and URL remain under `source`; provider-neutral state is under `outcome`:

| External state | Neutral outcome |
|---|---|
| GitLab `opened` | `open`, non-terminal |
| GitLab `closed` | `closed`, terminal |
| Jira `To Do`, `Open`, `In Progress` | `open`, non-terminal |
| Jira `Done`, `Closed` | `closed`, terminal |

Unmapped states fail closed. Add a reviewed profile mapping rather than guessing from a provider label.

## GitLab

Prerequisites for live use are Agora Core's reviewed `gitlab-issues`, `gitlab-merge-requests`, and `gitlab-ci` adapters, a compatible `glab` CLI, and an externally managed CLI session or environment credential. Installation grants no provider authority.

The default `read-only` mode permits issue, merge-request, and pipeline reads. `delivery-write` permits issue comments/transitions and merge-request creation/comments only after an explicit capability grant and confirmation. `pipeline-control` separately protects destructive cancellation.

Issue creation, merge-request approval/request-changes/merge, and pipeline trigger are unsupported because the installed Core adapters cannot preserve the neutral operation contract. The profile returns `gitlab.operation.unsupported`; it never substitutes a shell or API call.

A delivery observation binds one issue, merge request, approval, and successful head pipeline to an exact commit and branch. Stale, failed, unbound, or wrong-branch pipelines and draft, unapproved, or closed-unmerged reviews remain blockers. The profile does not execute `glab` itself.

## Jira

Prerequisites for live use are Agora Core's reviewed `jira` adapter, a compatible Atlassian CLI (`acli`), and an externally managed authenticated Jira site. The profile stores no credential or site token.

The default `read-only` mode permits search and view. `work-write` permits create, comment, and transition only after an explicit `issue.write` or `issue.transition` grant plus confirmation. The normalizer consumes only `key` and the bounded `status` field requested by Core's view adapter; it constructs the work-item reference from the validated Jira site scope and key. Capture time is collector metadata, not an assumed Jira response field. Review, CI, repository, and Agora lifecycle operations are unsupported. Jira workflow permissions, conditions, and validators still apply after flavor authorization.

## Failures

Policy denial returns blockers such as `<provider>.mode.denied`, `<provider>.capability.missing`, and `<provider>.confirmation.required`. Unsupported or unknown operations raise stable `<provider>.operation.*` errors. Malformed or unsafe external facts use `integration.fact.*`; provider delivery blockers remain in the normalized observation. These categories stay distinct so an external outage or malformed response cannot be reported as an Agora policy decision.

## Offline samples

```bash
uv run agora-ai-sdlc run-sample gitlab-delivery
uv run agora-ai-sdlc run-sample jira-work-items
```

The samples install reviewed adapters in temporary repositories and prepare read-only Core invocations, but do not launch provider CLIs or require accounts, network access, or credentials. Their fixtures demonstrate equal normalized work-item outcomes and independent Agora lifecycle authority.
