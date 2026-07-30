# Herdr Orchestrator Simplification Design

## Status

Approved in conversation on 2026-07-30. This document defines the replacement
architecture; it does not approve implementation.

## Problem

The runtime added after `2547d9b` introduced dynamic task names, a separate
runtime registry, additional pool recovery state, and more controller routing
state. From `2547d9b` to `cf3abac`, the package added roughly 4,300 lines across
44 files.

The resulting contracts conflict:

- dispatch requires a role/task rename before the first prompt;
- a cold Codex worker has no session until after its first prompt;
- `next_controller_action.py` expects accepted implementation receipts even for
  a fresh Standard run;
- P1 is told to return after one tick, but not every flow proves that a watcher
  can wake it again;
- control state, worker-pool state, and the runtime registry each persist
  overlapping session, pane, name, and ownership facts;
- routing forbids the receipt awaiter while the package still maintains both an
  awaiter and a watcher.

The 152-test suite passed while a live cold-pool rename failed. Unit coverage of
individual helpers therefore does not prove the workflow.

## Goals

- Restore the reliable behavior present before dynamic naming runtime changes.
- Keep P1 responsive and controller-only.
- Preserve warm P2-P4 workers and on-demand P5-P9 gates.
- Recover a moved or closed lane without disturbing healthy siblings.
- Keep every P1 and worker inside one Herdr workspace.
- Make the runtime small enough to reason about and test end to end.
- Compare every skill candidate with the frozen Superpowers baseline.

## Non-goals

- Recover live lane sessions across a full Herdr restart.
- Encode task names or status in the Herdr agent name.
- Adopt agents, state, receipts, or events from another workspace.
- Preserve the current dynamic naming registry or its migration path.
- Rewrite public Git history.

## Replacement Strategy

Build the replacement on the behavior at `2547d9b`, then port only the
approved invariants from later work. Do not merge the pending cold-name fix
`b023a4d`; the replacement removes the rename-before-prompt architecture that
the fix extends.

The final delivery is a forward commit on the current branch. Implementation
must not reset or force-push public history.

## Architecture

### One mutable workspace ledger

Each Herdr workspace has one mutable `workspace-state.json`. It contains:

- the P1 controller session;
- fixed P2-P9 role slots and their current sessions;
- the active run, lanes, generations, dependencies, and owned paths;
- watcher identity, heartbeat, and event queue;
- pending requests and capacity/ownership queues.

Immutable lane receipts and Git artifacts remain separate. There is no runtime
name registry and no second mutable scheduler or pool ledger.

Herdr live state is authoritative for current pane location, agent status, and
liveness. The ledger records stable slot/session/run identity and updates pane
location during reconciliation.

### Fixed role names

Agents are named once when started:

| Slot | Display name |
|---|---|
| P1 | `p1_orchestrator` |
| P2 | `p2_impl` |
| P3 | `p3_impl` |
| P4 | `p4_impl` |
| P5 | `p5_integration` |
| P6 | `p6_review` |
| P7 | `p7_qc` |
| P8 | `p8_design` |
| P9 | `p9_persona` |

If another workspace already owns a display name, append the deterministic
workspace ID. Current task text belongs in Herdr status/task summary, not in
the name.

Delete task-slug naming, per-dispatch renaming, visible-name reservations,
legacy rename migration, and `runtime_registry.py`.

### P1 controller lifecycle

Invoking Herdr from an ordinary chat claims that chat as P1 when the workspace
has no live controller. A P2-P9 chat never promotes itself; it forwards the
request to the P1 inbox in the same workspace.

One controller tick performs:

1. reconcile the workspace ledger with live Herdr state;
2. ingest user requests and watcher events;
3. resolve ownership, dependencies, and available capacity;
4. emit every ready dispatch or gate action;
5. persist the new ledger revision atomically.

The reducer's return is internal. It is not permission for the assistant to
send a final response while delivery remains active.

New disjoint work uses an available slot immediately. Overlapping work queues
behind its owner. Capacity-limited work queues without blocking P1 from
analyzing later requests.

P1 may yield while workers run only when the watcher has a current heartbeat
and a proven P1 wake path. Otherwise P1 continues bounded monitoring and remains
available for user steering. P1 never implements, tests, integrates, reviews,
commits, pushes, or deploys.

### Watcher boundary

One watcher serves the live P1 lifecycle in a workspace. It may:

- inspect live Herdr agents and receipt paths;
- append immutable events and update its heartbeat;
- signal P1 when actionable work exists.

It may not mutate lane ownership, generation, acceptance, or dispatch state.
Only the controller reducer applies events to the workspace ledger.

Remove the legacy long receipt awaiter.

## Recovery

### Same-workspace move

When the same session appears at a new pane in the same workspace, update the
pane location and preserve the lane and generation.

### Closed or lost worker

A valid receipt persisted before loss wins. Otherwise, after three failed live
checks:

1. mark only that lane generation `LOST`;
2. supersede it;
3. retain healthy sibling lanes;
4. start a replacement in the same workspace and slot;
5. resume from the locked input and Git checkpoint.

### Foreign workspace

A session seen in another workspace is not a move. Mark the local lane lost and
start a local replacement. Never prompt, adopt, move, or share state with the
foreign workspace.

### Full Herdr restart

Create a new pool and run. Reuse only receipts and Git artifacts whose input
identity still matches. Do not revive old live session IDs.

### Cold start

Start each worker with its fixed role name and required native `--yolo`,
model, and effort. The first task prompt creates its Codex session; bind that
session afterward. No pre-prompt rename or name reservation is required.

A failed launch keeps the pane and retries the same slot. It must not close the
pane or create a naming quarantine flow.

## Receipt Identity

A receipt is bound to:

- contract;
- lane and generation;
- session;
- input identity;
- output artifact and verification.

Pane ID and display name are evidence, not validity keys. Moving a pane or
changing a harmless display suffix must not stale a completed receipt.

## Delivery Gates

Compact and Standard remain the only delivery gates.

- Compact uses P2-P4 for disjoint low-risk implementation and a read-only
  deterministic verifier. It does not load Standard recovery/review detail.
- Standard uses P5 for integration, P6 for integration review, and P7-P9 only
  when their predicates apply.

P1 never substitutes for a missing verifier, integration owner, reviewer, QC,
designer, or persona lane.

## Verification

The release gate must include workflow-level scenarios through the same public
helpers used in production:

1. cold P2-P4 start, first prompt, and session bind;
2. new disjoint work dispatched while existing workers remain busy;
3. same-workspace pane move preserves lane/session;
4. pane closure replaces only the lost lane;
5. foreign-workspace agents are never adopted;
6. missing watcher proof keeps P1 monitoring instead of finalizing.

Unit tests remain useful but cannot replace these scenarios. A live canary must
run in an isolated Herdr test session and must not target another user
workspace.

## Frozen Performance Baseline

The Superpowers baseline is immutable unless the user explicitly requests
rebaselining:

- compact three-lane task: `152s`;
- multi-module canary delivery: `1009s`.

After every skill change, rerun only the Herdr candidate:

- Compact must pass the shared acceptance and finish faster than `152s`.
- Multi-module must pass shared acceptance plus the locked deep-immutability
  probe and finish faster than `1009s`.
- Record results in a new SHA-addressed artifact; never overwrite history.
- Warn when a candidate is more than 10% slower than the best comparable Herdr
  result, even if it still beats Superpowers.

Store the baseline with a digest. Rebaseline only through an explicit user
decision.

## Complexity Gates

- Keep `SKILL.md` at or below 350 words.
- Compact must not load Standard-only recovery and review references.
- Maintain one mutable ledger, one identity extractor, and one atomic-write
  implementation.
- No stateful helper may simultaneously own pool lifecycle, naming, recovery,
  and migration.
- Duplicate session/workspace extraction and JSON-lock helpers are release
  findings.
- Remove superseded runtime modules instead of preserving inactive compatibility
  paths.

## Acceptance

The replacement is complete only when:

- all six workflow scenarios pass;
- Compact and Standard contract validators pass;
- independent code review reports no blocking state-ownership conflict;
- the frozen performance gates pass;
- the installed package matches the reviewed candidate;
- public main advances through a non-force forward update;
- no user Herdr pane is closed.
