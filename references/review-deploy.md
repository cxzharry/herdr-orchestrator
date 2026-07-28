# Review and deployment

Read this reference when runtime, browser, RBAC, persona, or deployment applies.

## Artifact and early gates

P5 publishes a full integration SHA, clean-tree receipt, content-based artifact
digest, effective environment fingerprint, and seed digest. Review only the
running artifact bound to that tuple.

P5 smoke and P6 review run concurrently. P5 proves every changed critical
journey renders without a setup/error fallback and each impacted role's critical
allowed action succeeds. P6 independently verifies integration provenance,
requirements, and the published artifact. Both receipts are required before
deployment.

## Deployment topology

P1 locks exactly one policy:

- **dev + main/production:** P5 deploys the verified artifact to dev. Main
  promotion waits for every applicable blocking gate.
- **single environment:** P5 deploys immediately after the early gates under a
  predeclared rollback or fix-forward policy.
- **no deployment target:** P5 starts an isolated local review runtime and
  reports artifact evidence without claiming deployment.

P1 authorizes promotion; P5 deploys. Reviewers never deploy or modify code.

## Parallel independent review

P7, P8, and P9 run concurrently after deployment. They may prepare charters,
fixtures, scripts, identities, and expected evidence as soon as the artifact is
published.

For full browser concurrency, provide a separate runtime, tenant, seed, browser
profile, and lock per reviewer while keeping one artifact digest. If isolation
is unavailable, serialize only browser-mutating segments; preparation, static
inspection, screenshot review, and evidence analysis continue in parallel.

Playwright alone is insufficient. Exercise all applicable system roles with
deterministic mock data. Reset an immutable seed before each independent
scenario. A role-aware matrix includes allowed, denied, boundary,
data-isolation, and cross-role handoff cases.

- P7 owns contract, functional, regression, failure-path, data-integrity, and
  applicable RBAC checks.
- P8 owns UI/UX, accessibility, responsiveness, error clarity, and unintended
  data-exposure review.
- P9 owns persona goals, critical journeys, cross-role experience, blockers,
  and friction.

P7 is always blocking. P8 and P9 are blocking when their scope applies and a
Critical or High finding remains. Medium and Minor findings continue as side
work unless the contract raises their severity.

## Findings and revision

Each reviewer reports PASS or one structured finding package to P1 and remains
read-only. P1 routes fixes to the owning lane.

Any code, config, migration, fixture, or seed mutation creates a new artifact
tuple and requires P6 re-attestation. Rerun the impacted review matrix plus the
locked critical smoke, not unrelated scenarios. A Critical or High finding
after single-environment deployment triggers the locked rollback or fix-forward
policy.

Before delivery, stop disposable review runtimes, confirm processes and sockets
are gone, and reconcile the original workspace to its locked baseline.
