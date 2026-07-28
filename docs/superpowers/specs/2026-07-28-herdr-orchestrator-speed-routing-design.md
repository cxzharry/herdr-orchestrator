# Herdr Orchestrator Speed and Skill Routing Design

## Goal

Reduce wall-clock delivery time and agent drift without weakening independent
verification. Keep Herdr as the sole scheduler, make each lane invoke the right
skill at the right phase, and release downstream work as soon as its actual
prerequisites pass.

## Success criteria

- The topology has at most nine panes.
- P5 and P6 no longer carry ambiguous, overlapping review goals.
- Every dispatched lane receives an explicit skill chain and exit contract.
- Independent work runs concurrently; no global phase barrier waits for
  unrelated side work.
- P5 smoke plus P6 approval releases deployment according to the locked
  environment topology.
- P7, P8, and P9 can review concurrently against the same immutable artifact.
- `SKILL.md` is a thin router; detailed references load only when applicable.
- Existing Git ownership, mock-data, role, Playwright, and evidence guarantees
  remain enforceable.

## Non-goals

- Do not add nested Codex subagents inside Herdr panes.
- Do not replace Herdr with Superpowers execution orchestration.
- Do not make every review advisory.
- Do not introduce a generic workflow engine or new deployment platform.

## Nine-pane topology

| Pane | Role | Model | Effort |
|---|---|---|---|
| P1 | Orchestrator | `gpt-5.6-sol` | `high` |
| P2 | Worker 1 | `gpt-5.5` | `medium` |
| P3 | Worker 2 | `gpt-5.5` | `medium` |
| P4 | Worker 3 | `gpt-5.5` | `medium` |
| P5 | Worker 4, then Integration Owner | `gpt-5.6-sol` | `high` |
| P6 | Integration Reviewer | `gpt-5.6-sol` | `high` |
| P7 | QC and regression | `gpt-5.6-sol` | `high` |
| P8 | Designer and UI/UX reviewer | `gpt-5.5` | `high` |
| P9 | User/Persona reviewer | `gpt-5.5` | `medium` |

P5 must exit its worker session and start a clean Integration Owner session in
the same pane. The new session receives only the locked contract and accepted
worker handoffs. P6 is independent of implementation and never edits the
artifact it reviews.

The existing graph remains the visual source of truth for style and topology:

- `assets/delivery-flow.excalidraw`
- `assets/delivery-flow.svg`
- `assets/delivery-flow.png`

The graph must be updated to show nine panes and the event-driven flow defined
below.

## Event-driven delivery flow

```text
P1 contract
    |
P2-P5 ready workers run in dependency waves
    |
P5 restarts as Integration Owner, integrates, and publishes one artifact
    |--------------------------|
P5 implementation smoke       P6 integration review
    |--------------------------|
             both pass
                 |
       P1 authorizes deployment
                 |
          P5 deploys target
         /        |        \
     P7 QC    P8 Designer   P9 Persona
         \        |        /
          applicable gates
                 |
        main promotion or delivery
```

P7-P9 may prepare charters, mock data, identities, scripts, and expected
evidence as soon as the artifact is published. They do not wait for deployment
to begin preparation. After deployment, their applicable reviews run in
parallel and each reports to P1 immediately upon completion.

There is no wait-for-all barrier for side work. A downstream node starts when
its declared prerequisites have receipts. Late side findings are routed to P1
without pausing unrelated work.

## Deployment policy

P1 locks the environment topology during the execution contract.

| Topology | P5 smoke plus P6 pass authorizes | Final promotion |
|---|---|---|
| Separate `dev` and `main`/production | Deploy the verified artifact to `dev` | Wait for every applicable blocking gate |
| One deployment environment | Deploy the verified artifact immediately | Critical or High findings trigger the predeclared rollback or fix-forward policy |
| No deployment target | Start an isolated local review runtime | Deliver the artifact and evidence only |

P1 authorizes promotion. P5 performs deployment. Reviewers never deploy and
never modify production code.

Before a single-environment deployment, the contract must name a tested
rollback command or an explicit fix-forward policy. Missing recovery evidence
blocks that deployment.

## Lane brief contract

P1 dispatches every role with this exact shape:

```text
ROLE:
GOAL:
REQUIRED SKILLS:
INPUTS / BASE SHA / ARTIFACT DIGEST:
WRITABLE PATHS:
PREREQUISITES:
DONE EVIDENCE:
DO NOT:
STOP / ESCALATE WHEN:
```

The brief names skill invocations in execution order. Conditional skills include
their observable trigger. A lane must not load every possible skill up front.

## Skill routing

| Role or event | Required skill chain |
|---|---|
| P1 before delivery design | `superpowers:brainstorming` |
| P1 after the written design is approved | `superpowers:writing-plans` |
| P2-P5 implementing behavior | `superpowers:test-driven-development` |
| Any implementation lane encountering a failure | `superpowers:systematic-debugging` |
| P5 using isolated Git lanes | `superpowers:using-git-worktrees` |
| An owning lane receiving P6-P9 findings | `superpowers:receiving-code-review` |
| Any pane before a handoff, PASS, publish, or completion claim | `superpowers:verification-before-completion` |
| Branch disposition is not already locked | `superpowers:finishing-a-development-branch` |

Invoking `$herdr-orchestrator` preselects Herdr as the execution harness.
Therefore P1 does not ask the `writing-plans` execution-mode question again.

These Superpowers skills must not be invoked inside the workflow:

- `dispatching-parallel-agents`
- `subagent-driven-development`
- `executing-plans`
- `requesting-code-review`

They create nested schedulers or reviewers. Herdr and the fixed P1/P6-P9 roles
replace those mechanisms. Their general independence and review principles may
inform the contract, but their dispatch procedures do not run.

P1 completes the full brainstorming workflow on every run, including written
spec review, before invoking `writing-plans`. Herdr is already the
user-selected execution mode, so the plan transitions directly into lane
routing after approval.

## Reviewer boundaries

### P6 Integration Reviewer

Verify the locked base, accepted worker SHAs, ownership, final diff, artifact
identity, deployment input, and integration evidence. P6 returns PASS or a
finding package; it does not fix code or run open-ended root-cause work.

### P7 QC

Run contract, regression, failure-path, data-integrity, and applicable RBAC
checks. Invoke systematic debugging only to produce a bounded reproducer and
root-cause boundary. Route the finding to its owning lane rather than fixing it.

### P8 Designer

Review applicable UI states and viewports for usability, accessibility,
responsiveness, error clarity, and unintended data exposure.

### P9 Persona

Run each applicable persona goal and cross-role journey. Report blockers and
friction separately so P1 can distinguish release failures from improvements.

P7 is always a blocking gate. P8 and P9 are blocking only when UI or persona
scope is applicable and the finding is Critical or High. Medium and Minor
findings continue as side work unless the execution contract explicitly raises
their severity.

## Parallel browser review

P7-P9 must use the same artifact digest but separate:

- runtime or test tenant;
- deterministic seed snapshot;
- browser profile;
- Playwright lock and evidence directory.

With isolated review environments, all three browser suites may run
concurrently. If isolation is unavailable, only browser-mutating segments use a
shared mutex. Charter preparation, static inspection, screenshot review, and
evidence analysis continue in parallel.

Each reviewer must exercise all applicable system roles with deterministic mock
data. A role-aware review includes allowed, denied, boundary, and cross-role
handoff cases.

## Failure and invalidation

- A reviewer reports one structured finding package and returns control to P1.
- Repeating the same blocker twice without new evidence triggers reassignment or
  user escalation; it does not start an unbounded loop.
- P1 routes fixes to an owning worker lane. Reviewers remain read-only.
- A new code, config, migration, fixture, or seed artifact requires P6 to
  re-attest the new artifact.
- P7-P9 rerun the impacted matrix plus the locked critical smoke, rather than
  blindly repeating unrelated scenarios.
- A Critical or High finding after a single-environment deployment triggers the
  locked rollback or fix-forward policy.

## Progressive disclosure

Replace the mandatory monolithic runtime-contract read with:

```text
SKILL.md
references/
  routing.md
  git-integration.md
  review-deploy.md
  high-assurance.md
```

`SKILL.md` should contain only the core invariant, pane roster, event router,
lane-brief shape, and conditional reference map. Target roughly 300 words.

- Read `routing.md` for every run.
- Read `git-integration.md` only for multiple writers, integration, or
  worktrees.
- Read `review-deploy.md` only when runtime, browser, RBAC, persona, or
  deployment applies.
- Read `high-assurance.md` only for security-sensitive, destructive,
  production-critical, or explicitly strict work.

Do not duplicate a Superpowers procedure in these references. Name the required
skill and keep only Herdr-specific adaptations.

## Validation strategy

Before editing the skill, run baseline scenarios against the current version and
record the observed delay or goal drift:

1. Four independent implementation lanes with one integration conflict.
2. A UI/RBAC task with mock roles and three reviewer perspectives.
3. A backend-only task where Designer and Persona are not applicable.
4. A single-environment deployment with a late Critical reviewer finding.

Forward-test the revised skill with fresh agents using the same raw scenarios.
Verify:

- each lane invokes only its prescribed skills;
- no nested agent scheduler appears;
- P5 changes session before integration;
- P6 remains read-only and reaches a bounded verdict;
- deployment begins after the correct P6 receipt;
- P7-P9 work concurrently when isolation exists;
- repeated blockers stop after the defined threshold;
- the final evidence references one artifact digest.

Run the existing structural, graph, syntax, and exact-render validators before
commit. The revised graph must preserve connected arrows, canonical assets, and
the two-role visual treatment while showing nine panes.
