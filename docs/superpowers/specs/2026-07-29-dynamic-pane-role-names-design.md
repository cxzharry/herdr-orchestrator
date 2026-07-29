# Dynamic Pane Role Names Design

**Status:** Approved, extended for concurrent-space isolation on 2026-07-29

**Scope:** Make every Herdr agent name show both its P1-P9 slot and its current
delivery role/task without changing stable slot, session, ownership, or receipt
identity.

## Problem

The current runtime names agents `hdr_p1` through `hdr_p9`. Those names expose
the logical slot but not the work assigned to the pane. A user looking at
Herdr cannot distinguish an auth implementation lane from a schema lane, or
tell when P5 has changed from Worker 4 to Integration Owner.

The delivery graph documents canonical roles, but the live pane names do not.

## Decision

Use the live Herdr agent name as a short dynamic display label:

```text
p{slot}_{role_slug}_{task_slug}
```

Examples:

- `p1_orchestrator`
- `p1_orchestrator_a1b2` when another space already has a live P1
- `p2_impl_auth`
- `p3_impl_schema`
- `p4_verify_checkout`
- `p5_integration_owner`
- `p5_deploy_dev`
- `p6_integration_review`
- `p7_qc_rbac`
- `p8_ui_review`
- `p9_persona_admin`

Herdr names accept lowercase ASCII letters, numbers, `_`, and `-`, must begin
with a lowercase letter, and are limited to 32 characters. The formatter must
normalize and truncate slugs deterministically.

## Alternatives Rejected

### Keep `hdr_pN` and change only the terminal title

This preserves existing name assumptions but does not guarantee that Herdr's
agent list or sidebar shows the role. It also creates two competing labels.

### Use fixed role names only

Names such as `p2_worker` or `p8_designer` identify the canonical role but do
not show what the pane is currently handling.

### Include lifecycle status in the name

Names such as `p2_impl_auth_working` duplicate Herdr's native
`working`/`idle`/`done` state and would cause unnecessary rename churn.

## Identity Model

Dynamic agent names are display and targeting handles, not stable lane
identity.

Stable identity remains:

- logical slot: P1-P9;
- controller scope created for the main chat session;
- Codex session ID;
- current lane and generation;
- owned scope and input identity in control state.

Pane, workspace, terminal, status, and dynamic name may change. Rebinding a
moved pane uses the stable session and slot, then refreshes the current dynamic
name in control state. Receipts continue to bind the exact live name recorded
for that generation.

The controller must recognize a slot from structured state or the normalized
`p{slot}_` prefix. It must not depend on an exact fixed name such as `hdr_p2`.

## Naming Lifecycle

### Controller

The active main chat agent becomes P1 for its own controller scope. When only
one P1 exists, it may use `p1_orchestrator`. Concurrent spaces append the
shortest deterministic controller-scope suffix that makes the live name
unique, for example `p1_orchestrator_a1b2`. It keeps that controller scope
across deliveries and pane movement until ownership is explicitly transferred
or the process exits.

Controller identity is not socket-global. Multiple spaces may have independent
P1 sessions on the same Herdr socket. Inbox, scheduler state, watcher events,
worker pool, P5 integration ownership, and P6-P9 review receipts are keyed by
controller scope plus contract. A worker may live in a different workspace
after pane creation or movement, but its lease still belongs to exactly one
controller scope.

An unnamed main chat may promote even when another scoped P1 exists. A P2-P9
agent never guesses the nearest P1 by workspace or name; it forwards only to
the controller session recorded in its current lane/pool state.

### Warm implementation pool

Unassigned warm workers use:

- `p2_worker_ready`
- `p3_worker_ready`
- `p4_worker_ready`

Immediately before P1 dispatches a capsule, it renames the selected agent to
the assignment name. Rename success and live session identity must be
confirmed before prompting the worker.

When the worker reaches `idle` or `done`, it keeps the last assignment name so
the user can still see what it completed. The next assignment replaces the
name.

### P5 phase changes

P5 is renamed at every role boundary:

1. optional implementation: `p5_impl_<task>`;
2. fresh integration ownership: `p5_integration_owner`;
3. deployment/local review runtime: `p5_deploy_<target>`.

P5's session restart requirement before Integration Owner remains unchanged.

### Review lanes

P6-P9 names combine canonical review responsibility with the approved matrix:

- P6: `p6_integration_review`;
- P7: `p7_qc_<matrix>`;
- P8: `p8_ui_review` or another bounded design-matrix slug;
- P9: `p9_persona_<persona>`.

If no safe task slug can be derived, use the canonical role without inventing
product meaning.

## Task Slug Rules

The task slug comes from approved routing metadata, never from free-form
guessing:

1. prefer an explicit lane display slug;
2. otherwise use the lane ID;
3. otherwise use the canonical role only.

Normalization:

- lowercase;
- replace non-alphanumeric runs with `_`;
- trim leading/trailing separators;
- collapse repeated separators;
- truncate the task segment to fit the 32-character name limit;
- use a deterministic fallback such as `task` only when the normalized value
  is empty.

Names must remain unique among live agents. A collision appends the shortest
deterministic lane suffix that fits; it must not silently rename another live
agent.

## Dispatch and Recovery Flow

Before every prompt:

1. resolve the lane's stable slot and session;
2. compute the expected dynamic name;
3. rename the live agent when the name differs;
4. re-read live identity;
5. atomically update control state with the current name and pane;
6. prompt by the verified dynamic name.

After context compaction or restart, P1 must re-read its controller-scoped
control state and take only the next scheduler action. It must not infer that
"integration/review remains" and run code, tests, or browser checks itself.
When P5 is applicable, the scheduler returns a P5 dispatch; applicable P6-P9
review remains a separate recorded gate.

For a moved pane:

1. locate the stable session;
2. retain its slot, lane, generation, and expected role/task name;
3. rebind the new pane;
4. restore the expected dynamic name only if Herdr did not preserve it;
5. update control state without creating a new lane generation.

For a closed or lost pane, replacement follows the existing generation and
receipt rules. The replacement receives the expected dynamic name before work
is resumed.

## Observability

The runtime contract, README, and delivery graph must state that live names
follow `p{slot}_{role}_{task}`. The graph continues to show canonical P1-P9
responsibilities and adds a concise live-name legend; it does not attempt to
show project-specific task slugs.

P1 status output should include slot, current dynamic name, and state:

```text
P2 p2_impl_auth working
P3 p3_impl_schema done
P5 p5_integration_owner idle
```

## Compatibility

Existing runs containing `hdr_p1` through `hdr_p9` must be recoverable. On the
first scheduler tick after upgrade:

- map the legacy exact name to its slot;
- compute the expected current display name from durable lane metadata;
- rename and persist it;
- do not change session, lane generation, ownership, or accepted receipts.

New runs use dynamic names from bootstrap.

Legacy socket-global P1 state migrates to one controller scope owned by the
recorded P1 session. Another active main chat creates a separate scope; it does
not reuse, reset, or target lanes leased to the migrated controller.

## Verification

Test-first scenarios:

1. Baseline runtime exposes only `hdr_p2`; the observability assertion fails.
2. Dispatch renames a warm P2 lane before prompting it.
3. Different implementation assignments produce distinct bounded names.
4. P5 changes from implementation name to Integration Owner and deploy name.
5. A stable session moved to another pane retains or restores its dynamic
   name without a new generation.
6. Controller forwarding recognizes dynamic P2-P9 names and never promotes
   them to P1.
7. A legacy `hdr_pN` run migrates once without losing ownership or receipts.
8. Collision and 32-character truncation are deterministic.
9. Contract, asset, and exact-render validators pass with the naming legend.
10. Two spaces promote independent P1 sessions, dispatch same-numbered logical
    slots without live-name collision, and never reuse another scope's P5-P9.
11. After compaction, P1 routes integration verification to P5 and applicable
    QC/design to P7/P8 without editing or testing in the controller pane.

## Success Criteria

- Every live P1-P9 agent exposes a role-specific name.
- Implementation and applicable review panes expose the current task/matrix
  when approved metadata provides one.
- Rename happens before work dispatch.
- Each main chat has an independent P1 controller scope; concurrent names
  remain unique and role-readable.
- Pane movement and legacy migration preserve stable identity and active work.
- No lifecycle status is duplicated in the name.
- Existing Compact/Standard routing, receipts, P1 boundary, graph topology,
  and deployment behavior remain unchanged.
- P1 never implements, edits, tests, integrates, reviews, deploys, or performs
  browser verification, including after compaction.
