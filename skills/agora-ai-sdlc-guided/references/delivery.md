# Delivery — evidence and explicit branch/PR handoff

Collect current acceptance results, unresolved findings, changed paths, commits,
artifact revisions and review evidence. Compare the actual diff with the authorized
scope. The PR summary must agree with the current evidence; do not ask the user to
manually synchronize duplicate summaries when a deterministic projection suffices.

Keep all corrections in the iteration's recorded branch. A new iteration is not a
new prompt, review, or model session. Reuse a valid binding; do not work on main,
switch branches over dirty files, or create arbitrary branches to avoid a failed
precondition. Use available Core branch/Work operations; if they are unavailable,
report the limitation, not a fabricated binding.

Offer the PR handoff explicitly when delivery is ready: no changes -> explain;
existing PR -> show it; new PR -> present head/base, scope and evidence and request
explicit authorization to publish. Use the governed review tool adapter where
available. Opening a PR does not complete integration, acceptance or deployment.
Never auto-merge or silently close the source issue before its conditions hold.

Do not relabel a bypassed execution as authorized after the fact. Preserve the
exception and its linked remediation. A read-only observation suggesting delivery
review is not permission to push, open a PR, approve or merge.
