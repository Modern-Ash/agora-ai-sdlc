# Existing-codebase multi-LLM pilot

## Scope and evidence boundary

The executable pilot uses a small maintained Python catalog as the issue's permitted equivalent to a Java/Spring Boot fixture. It runs without a network, credentials, provider SDKs, or live models. Adapter-shaped fake processes are launched through real Agora Core sessions, so session persistence, runtime metadata, lifecycle gates, evidence, and validation are exercised while model quality is not.

Run it with:

```console
uv run agora-ai-sdlc run-sample existing-codebase-pilot
```

The JSON result exposes the baseline, rejected and accepted Git commits; producer and reviewer actor/runtime/provider/model provenance; the rejected and approved review decisions; the blocked gate; normalized CI categories bound to the accepted commit; and the installed Method Pack digest comparison.

## Offline flow

1. Establish the three-test baseline and explicit volume-pricing request.
2. Launch provider-alpha as producer; its four passing tests omit invalid-quantity coverage.
3. Launch provider-review as an independent reviewer; it returns `changes-requested` and review policy rejects the revision.
4. Attempt construction to operations before verification, evidence, and approval; the Core gate blocks.
5. Replace provider-alpha with provider-beta for the same producer actor, without reinstalling or changing the Method Pack.
6. Correct the behavior, run five tests, obtain an independent approval, and record four neutral CI facts for the accepted commit.
7. Complete acceptance and run Core validation.

## Metrics

Measured offline facts are the baseline/first/final test counts and outcomes, review-round count, gate-rejection count, exact Git revisions, provider identities, Method Pack digests, and lifecycle result. The pilot does not measure production defect rate, delivery lead time, operational performance, or semantic equivalence of live model output. Those remain explicit expectations, not findings.

## Optional live two-provider procedure

Live execution is operator-controlled and is never part of default CI.

1. Work in a disposable clone and record the installed Agora Core, adapter, and model versions.
2. Use the same `CHANGE_REQUEST.md`, fixture baseline, review profile, acceptance criteria, and Method Pack commit as the offline run.
3. Configure one authenticated provider for the producer and a different authenticated provider for the reviewer using local provider tooling. Do not place tokens, endpoint URLs, environment dumps, or raw restricted prompts in the repository or Agora artifacts.
4. Run definition and implementation with the producer. Record the resulting commit and Core session summary.
5. Run review in a fresh session with the second provider. Preserve only bounded provenance, verdict, findings, and non-secret evidence references.
6. Require a rejected revision to be corrected before approval; do not manufacture a rejection when the reviewer finds none. Record that outcome as a deviation from the offline scenario.
7. Run repository CI for the exact accepted commit, add its normalized evidence, obtain accountable human acceptance, and run `agora validate`.
8. Compare lifecycle transitions, review separation, test outcomes, token/cost observations, and elapsed delivery time with the offline baseline. Label every observation as measured and every extrapolation as an expectation.

A live pass applies only to the recorded provider, adapter, model, credential scope, repository revision, and date. It is not provider certification.
