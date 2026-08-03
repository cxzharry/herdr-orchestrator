# Herdr Orchestrator Deterministic Fast Path Design

## Status

Approved in conversation on 2026-08-03. This document approves the design,
not an unreviewed implementation.

## Problem

The runtime helpers are fast, but real delivery is slow. The current 85-test
suite completes in about 0.15 seconds while the active-session-selector run
took 4,393 seconds from run start to delivery receipt. Its implementation
receipts arrived at 647–742 seconds; integration, review, three QC lanes, and
delivery then ran mostly serially.

Four contract gaps cause avoidable orchestration latency:

1. Compact is described as requiring disjoint P2–P4 work, so a single small
   function has no explicit one-lane fast path and commonly falls into
   Standard.
2. `herdr-run-manifest/v1` does not require or persist `mode`, although the
   reducer prewarms P5/P6 only when `run.mode == "Standard"`.
3. `manage_worker_pool.py` emits an obsolete live command shape. Current Herdr
   requires `herdr agent start <name> --kind codex --pane <id> -- --yolo`.
   Fake-client tests do not exercise this boundary.
4. Applicable P7–P9 gates are often dispatched serially even when they inspect
   the same immutable candidate independently.

## Goals

- Make one-function and one-lane work take the shortest contract-safe route.
- Keep P1 controller-only and responsive to new requests while workers run.
- Preserve integration and independent QC for every implementation.
- Keep all agents and recovery inside the caller's Herdr workspace.
- Preserve fixed role names, dynamic task summaries, receipt identity, and
  pane move/close recovery without automatically closing panes.
- Make route selection and gate applicability machine-verifiable.
- Prove speed with a live single-function canary and the existing frozen
  Compact and multi-module scenarios.

## Non-goals

- Let P1 implement, test, integrate, review, commit, push, or deploy.
- Remove receipt gates or weaken candidate-bound independent QC.
- Add a global daemon, hook, or cross-workspace worker pool.
- Rename fixed P1–P9 roles.
- Change or rerun the frozen Superpowers baseline.
- Automatically close idle, failed, or completed panes.

## Deterministic Mode Contract

Every run manifest must include `mode`, exactly `Compact` or `Standard`, plus a
`review_applicability` object for P7, P8, and P9. Missing or unknown values are
validation errors; the runtime must not silently choose Standard.

Compact is valid for one to three implementation lanes when all are local,
low-risk, path-owned, and covered by deterministic checks. A single function
or single file is a first-class Compact run. Standard is required by any of:

- browser or visual behavior;
- auth, RBAC, security, privacy, or secrets;
- schema, migration, destructive, deployment, or external-state work;
- nondeterministic acceptance;
- an explicit high-assurance or broader review requirement.

The approved plan states the mode and the evidence for every predicate. A
contradictory plan is blocked before any worker starts.

## Delivery Waves

### Compact

1. Start only the P2–P4 implementation slots actually owned by the plan.
2. As soon as implementation begins, prewarm P5 integration and P6 independent
   QC concurrently.
3. P6 may inspect completed lane commits while sibling implementation remains
   active, but its terminal verdict binds the integrated candidate.
4. P5 integrates accepted commits and runs the deterministic acceptance.
5. P6 independently verifies the exact P5 candidate and receipt tuple.
6. P5 performs explicitly authorized delivery only after P6 PASS.

P7–P9 are not part of Compact. Independent QC remains P6 and is never replaced
by P1 or the implementation owner.

### Standard

1. Dispatch independent P2–P4 lanes concurrently and prewarm P5/P6 in the
   first controller tick.
2. P5 integrates while P6 reviews completed lane diffs where safe.
3. P6 gives a candidate-bound verdict on the integrated tree.
4. Applicable P7, P8, and P9 lanes start in one wave against the same immutable
   candidate and run concurrently.
5. P5 performs explicitly authorized delivery after every applicable receipt
   passes.

Blocking findings return only to the owning lane. Reruns are limited to the
changed candidate and impacted gates.

## Runtime Boundary Repair

`create_control_state.py` validates and persists mode and review applicability.
`controller_tick.py` emits the whole currently ready wave, including P5/P6
prewarm and concurrent applicable QC actions. No action executor is allowed to
run product commands in P1.

`manage_worker_pool.py` keeps state reconciliation separate from live pane
allocation. Its Herdr adapter must:

- create or reuse an available pane in the current workspace only;
- start Codex with the installed CLI shape and native `--yolo`;
- parse pane and agent identifiers from JSON results;
- preserve focus;
- never move to another workspace or close a pane;
- recover stale same-workspace bindings without adopting foreign agents.

At least one test must execute the command-construction boundary against the
installed Herdr help/CLI contract, not only a fake client.

## Performance Evaluation

Meta-harness locks these criteria:

- route correctness and preserved contracts;
- one-function cold and warm wall-clock latency;
- overlap of independent stages;
- live CLI compatibility and recovery;
- no regression in frozen scenario quality.

The new live micro-canary implements and verifies one deterministic function in
an isolated same-workspace fixture. Record cold and warm wall-clock timings,
phase timestamps, rework, exact candidate SHA, and acceptance output.

After each important candidate change, run the smallest meaningful focused
checks. At the final candidate only, rerun the existing Herdr Compact and
multi-module scenarios. Compare them with frozen Superpowers values of 152 and
1009 seconds without modifying or rerunning the baseline. Report any candidate
more than 10 percent slower than the best comparable Herdr result.

## Acceptance

The change is accepted only when:

- a single-function plan is deterministically classified Compact;
- manifests missing mode or applicability fail before dispatch;
- Compact creates only required implementation slots and overlaps P5/P6;
- every implementation passes P5 integration and P6 independent QC;
- Standard emits applicable P7–P9 work concurrently;
- the installed Herdr CLI start shape is covered and passes a live isolated
  canary;
- existing move, close, stale, same-workspace, watcher, receipt, and P1
  controller-only tests remain green;
- frozen Compact and multi-module quality gates pass and timings beat 152 and
  1009 seconds;
- source and installed skill trees match the reviewed candidate;
- main advances normally and no pane is closed by the runtime.
