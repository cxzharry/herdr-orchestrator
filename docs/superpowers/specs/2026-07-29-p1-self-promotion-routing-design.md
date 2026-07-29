# Persistent P1 Orchestration Design

**Status:** Approved direction, pending written-spec review

**Scope:** Make the current eligible chat agent a persistent, non-blocking P1
controller; keep implementation, verification, integration, review, and deploy
outside P1.

## Goal

P1 remains responsive while P2-P9 work. When the user gives P1 another task,
P1 classifies it, protects active path ownership, and dispatches or queues new
work without interrupting existing lanes.

P1 is an orchestrator only. It may reason about routing metadata but must not
inspect product code deeply, implement, verify product behavior, integrate,
review, commit, push, or deploy.

## Terminology

- `hdr_p1`: the one persistent controller in a Herdr session.
- P2-P4: reusable implementation or analysis workers.
- P5: optional Worker 4 before integration, then a fresh Integration Owner.
- P6: independent integration reviewer.
- P7: functional and browser QC.
- P8: UI and motion reviewer.
- P9: persona and RBAC reviewer.
- Delivery delta: a new direct user request accepted into an active delivery
  without rewriting the entire approved plan.
- Scheduler tick: one bounded P1 pass that ingests events and requests,
  updates dependency state, dispatches ready work, and returns control.
- Run watcher: one non-agent process scoped to a delivery that observes
  receipts and liveness without blocking P1.

The `p1` segment in a pane ID such as `w5:p1` is not a role. Live controller
identity comes from Herdr agent name plus pane, terminal, and Codex session.

## Controller Lifecycle

At orchestration entry:

| Current identity | Existing live `hdr_p1` | Result |
|---|---|---|
| `hdr_p1` | self | Continue as controller |
| P2-P9 or another named agent | present | Forward to P1; never promote |
| P2-P9 or another named agent | absent | Block; never promote |
| unnamed current agent | absent | Eligible to self-promote |
| unnamed current agent | present | Forward to the existing P1 |

An eligible unnamed agent self-promotes only after the initial delivery inputs
are approved and valid. Promotion renames the same live agent to `hdr_p1` and
rechecks the exact pane, terminal, and Codex session.

P1 persists after one delivery finishes so the user can continue assigning
work. It relinquishes the role only when its Codex process exits or the user
explicitly ends or transfers controller ownership. Pane movement does not
change controller ownership.

## Strict P1 Boundary

P1 may:

- read approved plans, request envelopes, lane metadata, receipts, and evidence
  indexes;
- validate root, base SHA, input digest, ownership, dependencies, risk, and
  gate predicates;
- inspect live Herdr agent state;
- classify work, allocate capacity, dispatch capsules, and route findings;
- supersede or replace a lost lane without touching product bytes;
- report decisions, blockers, accepted evidence, and queue state.

P1 must not:

- read product source to derive an implementation;
- edit product, test, configuration, documentation, or migration files;
- run product tests, builds, browser checks, or deployment commands;
- resolve code conflicts or integrate worker changes;
- perform code, UI, functional, or persona review;
- commit, push, deploy, or mutate external product state;
- wait synchronously on a worker or receipt for a long interval;
- invent architecture or silently broaden a plan.

P1 may run only control-plane helpers and bounded repository metadata checks.
When source discovery is required, P1 dispatches an analysis-only capsule to an
available implementation worker. That worker returns affected paths,
dependencies, risks, and recommended ownership without editing.

## Non-Blocking Scheduler

P1 does not call a long `await_receipts` operation in its own turn. Every P1
turn is one bounded scheduler tick:

1. Read queued watcher events and forwarded requests.
2. Ingest the current user request.
3. Reconcile live lane identity and terminal receipts.
4. Classify each new work item as dispatchable, dependency-blocked,
   capacity-blocked, analysis-required, or plan-required.
5. Atomically register newly accepted lanes and ownership.
6. Dispatch all currently ready independent lanes without `--wait`.
7. Return a short status containing active, newly dispatched, queued, and
   blocked work.

No scheduler tick waits for implementation completion. The next tick is
triggered by a user message or a safe watcher signal.

## Run-Scoped Watcher

Each active delivery has one small Python watcher process, not an LLM agent and
not a permanent daemon. It exits when its delivery reaches a terminal state.

The watcher:

- monitors receipt files and live agent/session identity;
- emits immutable events for terminal receipt, moved pane, lost lane, and
  watcher failure;
- never edits product files, lane generations, or ownership;
- never interprets acceptance evidence;
- never prompts a working or blocked P1;
- signals an idle/done P1 with only an event ID;
- leaves events queued when P1 is busy.

P1 claims watcher events at the start of the next scheduler tick. Event claims
are idempotent and bound to the current P1 session.

This replaces the current design where P1 blocks inside
`await_receipts.py --timeout 600`.

## Dynamic Work Intake

### Approved delivery delta

A direct user request is accepted as a delivery delta without another plan
approval when all are true:

- it is implementation, verification, review, or deploy work inside the
  current repository and product scope;
- the request is sufficiently clear to derive bounded acceptance;
- it does not change architecture, security policy, schema or migration
  topology, or production deployment topology;
- P1 can assign disjoint ownership or an explicit dependency on an existing
  owner;
- applicable review predicates can be selected deterministically.

The exact user message is the immutable source of the delta. P1 adds only
routing metadata: delta ID, owned paths, dependencies, gate, acceptance,
checks, and applicable roles.

### Plan-required delta

P1 returns `PLAN_REQUIRED` instead of dispatching when the request changes:

- architecture or public contracts;
- security, authentication, authorization, or RBAC policy;
- database schema or migration topology;
- production environment or deployment topology;
- unclear product behavior requiring brainstorming or a user choice.

Active lanes continue while a new delta awaits planning or approval.

## Ownership and Capacity

For each new task:

1. If affected paths are known and disjoint, dispatch to an idle worker.
2. If paths overlap an active lane, queue behind that owner or append a bounded
   compatible capsule to the same worker after its current receipt.
3. If paths are unknown, use an analysis-only worker before mutation.
4. If all implementation capacity is busy, keep the lane `READY` and return
   immediately.

Capacity order:

1. Reuse idle P2-P4.
2. Use P5 as Worker 4 only before integration ownership begins.
3. Before P5 becomes Integration Owner, restart it into a fresh session.
4. P6-P9 never become implementation workers.

P1 never edits a lane merely because capacity is unavailable.

## Compact Delivery Without P1 Implementation

Compact no longer asks P1 to rerun product checks.

```text
one implementation lane:
  P2 implement -> P3 independently verify

two implementation lanes:
  P2 + P3 implement -> P4 independently verify combined result

three or more implementation lanes:
  upgrade to Standard
```

The Compact verifier is read-only. It checks exact scope, diff identity, and
deterministic acceptance, then returns a terminal verification receipt. P1
accepts or routes that receipt without executing the checks itself.

## Standard Delivery Without P1 Implementation

- P2-P4 implement or perform analysis-only discovery.
- P5 integrates accepted worker outputs, resolves conflicts, runs the complete
  test/build suite, commits, pushes, and deploys when applicable.
- P6 independently reviews the integrated artifact.
- P7 runs functional/browser QC when applicable.
- P8 runs UI/motion review when applicable.
- P9 runs persona/RBAC review when applicable.
- P1 routes every finding back to its owning implementation lane.

Only P5 mutates the integrated artifact after implementation handoff.

## Requests Received in Worker Panes

P2-P9 never self-promote.

When a worker receives work outside its lane:

1. Preserve its active lane and context.
2. Persist an exact request envelope in the socket-scoped P1 inbox.
3. If P1 is idle/done, signal it with the request ID only.
4. If P1 is working/blocked, leave the request queued.
5. Reply `FORWARDED` or `QUEUED` with the request ID.

Do not inject request content into a working P1; that could steer or replace
its active scheduler tick.

## State Model

Standard control state adds:

- exact P1 identity;
- delivery delta records;
- lane ownership and dependencies;
- scheduler status: `READY`, `ACTIVE`, `DEPENDENCY_BLOCKED`,
  `CAPACITY_BLOCKED`, `PLAN_REQUIRED`, or terminal;
- watcher event queue and claim identity.

Only P1 changes routing states. Workers write terminal receipts. The watcher
writes observation events. P5 writes integration/deployment evidence.

Compact uses a smaller socket-scoped scheduler state containing controller,
delta, implementation lane, verifier lane, and receipt identities. P1 still
does not run product checks.

## Failure Handling

- No Herdr environment: `BLOCKED_NOT_IN_HERDR`.
- Named worker with no P1: `BLOCKED_NO_CONTROLLER`.
- Another named agent attempts promotion: `BLOCKED_ROLE_CONFLICT`.
- Duplicate delta/request/event: return its existing state.
- Lost worker: watcher emits `LANE_LOST`; P1 supersedes only that generation.
- Moved pane with stable session: watcher emits `LANE_MOVED`; P1 rebinds it.
- Watcher exits unexpectedly: P1 starts one replacement watcher without
  changing lane generations.
- P1 exits: workers keep durable receipts and state; a replacement controller
  must explicitly recover the run before dispatching new work.
- New request overlaps active ownership: queue it; never permit concurrent
  mutation of the same paths.
- Task requires a new plan: mark only that delta `PLAN_REQUIRED`; unrelated
  lanes continue.

## Components

### Controller router

Resolves live roles, promotes an eligible unnamed agent, forwards worker
requests, and owns the P1 request inbox.

### Scheduler state helper

Atomically registers delivery deltas, lanes, dependencies, ownership, capacity,
and transitions. It does not inspect product code.

### Run watcher

Waits on receipts/liveness outside P1 and appends immutable events.

### Runtime contract

Defines the strict P1 boundary, scheduler ticks, dynamic delta policy, Compact
verifier topology, Standard ownership, and safe event signalling.

## Verification

Unit tests must cover:

1. Eligible unnamed agent self-promotes with stable session identity.
2. P2-P9 never self-promote and safely forward.
3. P1 scheduler tick returns without waiting for active workers.
4. User can submit a second delta while P2/P3 are active.
5. Disjoint delta dispatches to an idle P4.
6. Overlapping delta queues behind the owning lane.
7. Unknown paths create analysis-only work.
8. Full capacity produces `CAPACITY_BLOCKED` without blocking P1.
9. Low-risk direct request becomes an approved delivery delta.
10. Architecture, security, schema, and production-topology changes become
    `PLAN_REQUIRED`.
11. Watcher queues events while P1 works and signals only settled P1.
12. Receipt, move, close, and watcher-failure events are idempotent.
13. Compact uses a worker verifier and never executes product checks in P1.
14. Standard assigns integration/test/commit/push/deploy to P5.
15. Static contract validation rejects P1 product mutation or long waits.

Live canary:

1. Promote the current eligible agent to `hdr_p1`.
2. Dispatch independent work to P2 and P3.
3. While both work, submit another user delta to P1.
4. Verify P1 returns promptly and dispatches disjoint work to P4.
5. Submit an overlapping delta and verify it queues behind its owner.
6. Complete receipts through the watcher without a blocking P1 wait.
7. Verify P5 integrates and runs acceptance while P1 only routes.

## Non-Goals

- Letting P1 implement, test, review, integrate, commit, push, or deploy.
- Treating pane ID `p1` as controller identity.
- Allowing P2-P9 to self-promote.
- Adding a permanent daemon or another LLM scheduler.
- Interrupting a working P1 with raw request or receipt content.
- Automatically approving architecture, security, schema, or production
  topology changes.
- Rewriting Superpowers brainstorming or planning inside Herdr Orchestrator.
