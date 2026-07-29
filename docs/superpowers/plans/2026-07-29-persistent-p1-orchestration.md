# Persistent P1 Orchestration Implementation Plan

> **For Codex:** Execute this plan with `herdr-orchestrator` after approval.
> The active chat agent becomes P1 and owns no product or skill files. P1 only
> validates, dispatches, reconciles, and reports. P2-P5 implement and integrate;
> P6-P8 provide independent review and visual evidence.

**Goal:** Make the current eligible agent a persistent, non-blocking,
orchestration-only P1 that can distribute new work while existing Herdr lanes
continue, with measured quality and speed against locked baselines.

**Architecture:** A socket-scoped controller router binds one live `hdr_p1`.
Each delivery has an atomic scheduler state and a run-scoped non-agent watcher.
P1 runs bounded scheduler ticks; workers and reviewers own every product
mutation and check. Compact uses a separate verifier. Standard converges at P5,
then passes applicable P6-P9 gates.

**Tech stack:** Python 3 standard library, Herdr CLI, Markdown skill contracts,
Excalidraw JSON, SVG, deterministic Chrome/Pillow rendering, `unittest`.

## Herdr Delivery Contract

- **Controller:** the current eligible unnamed agent self-promotes to
  `hdr_p1`; a named P2-P9 agent never promotes and forwards to the existing
  controller.
- **P1 owned paths:** none. P1 may read only approved inputs, runtime metadata,
  receipts, evidence indexes, and test summaries.
- **Implementation lanes:** P2 owns controller identity/inbox helpers; P3 owns
  scheduler state and delta classification; P4 owns watcher/event helpers and
  benchmark harness. Paths are disjoint.
- **Integration lane:** P5 accepts validator-clean receipts, integrates all
  changes, resolves conflicts, runs the full suite, renders assets, commits,
  installs the verified skill, and performs any approved push/deploy.
- **Independent gates:** P6 reviews the integrated contract and diff; P7 runs
  the live distribution/recovery canary; P8 visually reviews the graph PNG and
  checks that it matches the runtime contract. P9 is not applicable because
  this change has no product persona/RBAC behavior.
- **Isolation:** implementation lanes use dedicated worktrees from the same
  locked base SHA. No two lanes own the same file.
- **No nested orchestration:** workers execute their capsule directly and do
  not summon agents or broaden scope.
- **Agent launch:** every newly started Codex worker or reviewer uses the
  existing model roster and appends `-- --yolo` to `herdr agent start`.
- **Failure routing:** P1 routes each finding to the owning lane. Only impacted
  gates rerun. A lost worker increments only its lane generation.

## Locked Meta-Harness Inputs

Use `/Users/haido/.codex/meta-harness/herdr-persistent-p1-20260729/`.

- Intent: `IMPROVE`
- Mode: `Parallel agents`
- Maximum iterations: 3
- Composite target: 8.5/10
- Per-criterion success target: 8.5/10
- Per-criterion failure floor: 7.0/10
- Primary baseline:
  `b80be3e36fd4e1a00e22543b6bc913212085079e`
- Secondary baseline: original Superpowers without Herdr
- Minimum trials: 3 per applicable implementation

The rubric is immutable after implementation starts. Evaluators score evidence,
not implementer self-reports.

---

### Task 1: Freeze Baselines and Add RED Contract Tests

**Files:**

- Create: `benchmarks/persistent-p1/scenario.json`
- Create: `benchmarks/persistent-p1/run_benchmark.py`
- Create: `scripts/test_controller_router.py`
- Create: `scripts/test_scheduler_state.py`
- Create: `scripts/test_run_watcher.py`
- Create: `scripts/test_p1_contract.py`
- Modify: `scripts/verify_contract.py`

**Step 1: Record the benchmark scenario**

Define one deterministic workload with two active disjoint lanes, one new
disjoint delta, one overlapping delta, and one architecture-changing delta.
Record exact inputs, expected ownership, expected state transitions, applicable
gates, and acceptance commands in `scenario.json`.

**Step 2: Write failing tests for controller identity**

Cover:

- unnamed eligible controller promotion;
- stable session recheck;
- existing `hdr_p1` reuse after pane movement;
- P2-P9 forwarding without self-promotion;
- `BLOCKED_NO_CONTROLLER` and `BLOCKED_ROLE_CONFLICT`.

Run:

```bash
python3 -m unittest scripts.test_controller_router -v
```

Expected: FAIL because the controller router does not exist.

**Step 3: Write failing scheduler tests**

Cover atomic delta registration, disjoint dispatch to P4, overlap queuing,
analysis-only discovery, capacity-blocked immediate return, plan-required
classification, idempotent request IDs, and preservation of active lanes.

Run:

```bash
python3 -m unittest scripts.test_scheduler_state -v
```

Expected: FAIL because scheduler state v2 does not exist.

**Step 4: Write failing watcher tests**

Cover receipt, moved-pane, lost-lane, duplicate-event, busy-P1 queueing,
idle-P1 event-ID signalling, replacement after watcher failure, and terminal
exit.

Run:

```bash
python3 -m unittest scripts.test_run_watcher -v
```

Expected: FAIL because the run watcher does not exist.

**Step 5: Add a static P1 boundary test**

Parse the skill and routing contract. Reject:

- P1 product mutation, product tests, build, browser, review, integration,
  commit, push, or deploy;
- long synchronous receipt waits in the P1 flow;
- Compact self-verification by P1;
- P1 shown as the deploy or publish owner.

Run:

```bash
python3 -m unittest scripts.test_p1_contract -v
```

Expected: FAIL against the current contract.

**Step 6: Capture baseline evidence**

Create a detached worktree at the primary baseline and run its full contract
suite plus the benchmark adapter. Run the equivalent bounded workload through
original Superpowers as the secondary comparison. Store raw trial output under
the Meta Harness `reports/baselines/` directory; do not commit machine-local
timings.

**Step 7: Commit the RED harness**

```bash
git add benchmarks/persistent-p1 scripts/test_controller_router.py \
  scripts/test_scheduler_state.py scripts/test_run_watcher.py \
  scripts/test_p1_contract.py scripts/verify_contract.py
git commit -m "test: lock persistent P1 orchestration contract"
```

---

### Task 2: Implement Controller Identity and Safe Forwarding

**Files:**

- Create: `scripts/controller_router.py`
- Create: `scripts/test_controller_router.py`
- Modify: `references/routing.md`

**Step 1: Implement pure identity decisions**

Expose a pure function that accepts current agent identity, current pane and
session, and the discovered live `hdr_p1`, then returns exactly one action:
`CONTINUE`, `PROMOTE`, `FORWARD`, or `BLOCK`.

**Step 2: Implement socket-scoped inbox envelopes**

Persist the exact user request plus routing metadata under the live Herdr
socket identity. Use atomic create/replace and deterministic request IDs.
Signal only an idle/done P1, and send only the request ID.

**Step 3: Implement promotion verification**

Rename the same live agent to `hdr_p1`, then re-read agent, pane, terminal, and
Codex session identity. Fail closed if any identity changes unexpectedly.
Never infer role from a pane ID such as `w5:p1`.

**Step 4: Run focused tests**

```bash
python3 -m unittest scripts.test_controller_router -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/controller_router.py scripts/test_controller_router.py \
  references/routing.md
git commit -m "feat: bind one persistent Herdr controller"
```

---

### Task 3: Implement Atomic Scheduler State and Delta Routing

**Files:**

- Create: `scripts/scheduler_state.py`
- Create: `scripts/test_scheduler_state.py`
- Modify: `scripts/create_control_state.py`
- Modify: `scripts/register_lane.py`
- Modify: `scripts/set_lane_state.py`
- Modify: `scripts/validate_lane_receipt.py`
- Modify: `scripts/test_create_control_state.py`
- Modify: `scripts/test_register_lane.py`
- Modify: `scripts/test_set_lane_state.py`
- Modify: `scripts/test_validate_lane_receipt.py`

**Step 1: Introduce control state v2**

Add:

- exact controller identity and claim;
- immutable request and delta records;
- owned paths and dependency edges;
- `READY`, `ACTIVE`, `DEPENDENCY_BLOCKED`, `CAPACITY_BLOCKED`,
  `PLAN_REQUIRED`, and terminal states;
- event cursor and watcher identity;
- monotonic revision for compare-and-swap writes.

Provide a one-way reader upgrade for v1 state; do not add a generic migration
framework.

**Step 2: Implement deterministic classification**

Classification consumes request metadata and affected paths returned by an
analysis lane. It must not read product source. Return `PLAN_REQUIRED` for
architecture, public contract, security/auth/RBAC, schema/migration,
production-topology, or ambiguous product behavior changes.

**Step 3: Implement ownership and capacity**

Dispatch known-disjoint paths to idle P2-P4, optionally P5 before integration.
Queue overlaps behind their owner. Unknown paths produce analysis-only work.
Full capacity produces `CAPACITY_BLOCKED` without waiting.

**Step 4: Preserve receipt identity**

Bind every lane and receipt to contract ID, lane ID, generation, agent, pane,
session, input identity, root, base SHA, and owned scope. Existing recovery
increments only the affected generation.

**Step 5: Run focused and regression tests**

```bash
python3 -m unittest scripts.test_scheduler_state \
  scripts.test_create_control_state scripts.test_register_lane \
  scripts.test_set_lane_state scripts.test_validate_lane_receipt -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/scheduler_state.py scripts/test_scheduler_state.py \
  scripts/create_control_state.py scripts/register_lane.py \
  scripts/set_lane_state.py scripts/validate_lane_receipt.py \
  scripts/test_create_control_state.py scripts/test_register_lane.py \
  scripts/test_set_lane_state.py scripts/test_validate_lane_receipt.py
git commit -m "feat: route dynamic delivery deltas atomically"
```

---

### Task 4: Replace Blocking P1 Waits with a Run-Scoped Watcher

**Files:**

- Create: `scripts/run_watcher.py`
- Create: `scripts/test_run_watcher.py`
- Modify: `scripts/await_receipts.py`
- Modify: `scripts/test_await_receipts.py`
- Modify: `references/routing.md`

**Step 1: Extract one-shot receipt reconciliation**

Keep `await_receipts.py` as a compatibility/helper surface for non-controller
use, but make P1 call only a bounded one-shot reconcile operation.

**Step 2: Implement immutable watcher events**

Append receipt, move, loss, and watcher-failure events with deterministic event
IDs. The watcher may observe state and signal P1 but may not change ownership,
generation, acceptance, or product files.

**Step 3: Implement safe signalling**

When P1 is idle/done, prompt it with only an event ID. When P1 is working or
blocked, leave the event queued. Never inject raw receipt or request content.

**Step 4: Prove bounded ticks**

Use a fake Herdr adapter and monotonic clock to assert that P1 reconciliation
returns without waiting for active lanes. No P1 code path may call the
600-second wait.

**Step 5: Run focused and regression tests**

```bash
python3 -m unittest scripts.test_run_watcher scripts.test_await_receipts -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/run_watcher.py scripts/test_run_watcher.py \
  scripts/await_receipts.py scripts/test_await_receipts.py \
  references/routing.md
git commit -m "feat: observe Herdr lanes without blocking P1"
```

---

### Task 5: Enforce Orchestration-Only P1 in the Skill Contract

**Files:**

- Modify: `SKILL.md`
- Modify: `references/routing.md`
- Modify: `references/plan-contract.md`
- Modify: `references/git-integration.md`
- Modify: `references/review-deploy.md`
- Modify: `references/high-assurance.md`
- Modify: `scripts/verify_contract.py`
- Create: `scripts/test_p1_contract.py`
- Modify: `README.md`
- Modify: `agents/openai.yaml`

**Step 1: Replace the entry workflow**

After approved inputs, resolve controller identity, self-promote only if
eligible, run one scheduler tick, dispatch without `--wait`, and return queue
state. State that P1 persists after delivery.

**Step 2: Replace Compact self-verification**

Define:

```text
one implementation lane: P2 implement -> P3 verify
two implementation lanes: P2 + P3 implement -> P4 verify
three or more implementation lanes: upgrade to Standard
```

P1 validates receipt identity only; it does not rerun product checks.

**Step 3: Assign all delivery work away from P1**

P5 integrates, tests, builds, commits, pushes, and deploys. P6-P9 perform
independent applicable review. P1 routes findings and records terminal state;
it never promotes product bytes itself.

**Step 4: Correct terminology and user guidance**

Describe Herdr as the terminal multiplexer/control transport and the skill as
the orchestration policy. Document automatic routing after an approved plan,
the persistent P1 behavior, worker-pane forwarding, and the fact that panes
remain open for reuse.

**Step 5: Run contract tests**

```bash
python3 -m unittest scripts.test_p1_contract -v
python3 scripts/verify_contract.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add SKILL.md README.md agents/openai.yaml references scripts/verify_contract.py \
  scripts/test_p1_contract.py
git commit -m "docs: make P1 a persistent orchestration-only controller"
```

---

### Task 6: Redraw and Validate the Delivery Graph

**Files:**

- Modify: `assets/delivery-flow.excalidraw`
- Modify: `assets/delivery-flow.svg`
- Modify: `assets/delivery-flow.png`
- Modify: `assets/manifest.json`
- Modify: `references/delivery-flow.md`
- Modify: `scripts/verify_assets.py`

**Step 1: Redesign as two planes**

Use file-based Excalidraw mode. Place the persistent P1 inbox, bounded scheduler
tick, ownership/dependency state, and watcher event queue in a control band.
Place P2-P9 implementation, verification, integration, review, and deploy in a
separate delivery band.

Show:

- new requests arriving while lanes are active;
- disjoint dispatch, overlap queue, capacity queue, and `PLAN_REQUIRED`;
- dashed asynchronous watcher signals;
- Compact verifier paths;
- Standard P5 integration/deploy and P6-P9 review;
- terminal evidence returned to P1 without placing P1 on the mutation path.

**Step 2: Update semantic validation**

Replace old node, edge, text, and role ownership invariants with the new graph
contract. Keep deterministic element ordering, bindings, role colors, and
source digests.

**Step 3: Render all assets**

```bash
python3 scripts/render_assets.py --write assets/delivery-flow.png
python3 scripts/verify_assets.py
```

Expected: PASS and exact manifest hashes.

**Step 4: Perform visual review**

Open the PNG at original detail. Check clipped text, overlaps, arrow routing,
control/delivery separation, P1 forbidden-path clarity, and legibility at fit
width. Repeat render/review until clean.

**Step 5: Commit**

```bash
git add assets references/delivery-flow.md scripts/verify_assets.py
git commit -m "docs: redraw persistent P1 delivery topology"
```

---

### Task 7: Run the Locked Benchmark and Meta-Harness Iterations

**Files:**

- Modify: `benchmarks/persistent-p1/run_benchmark.py`
- Create: `benchmarks/persistent-p1/README.md`
- Create: `benchmarks/2026-07-29-persistent-p1.json`
- Write runtime evidence under:
  `/Users/haido/.codex/meta-harness/herdr-persistent-p1-20260729/reports/`

**Step 1: Run deterministic helper trials**

Run at least three trials per applicable implementation and record median and
p95:

- scheduler tick time with active lanes;
- disjoint-delta time-to-dispatch;
- overlap time-to-queue;
- capacity-blocked time-to-return;
- total scenario wall-clock.

**Step 2: Run the live Herdr canary**

With P2 and P3 active, give P1 a disjoint delta and verify it reaches P4 without
waiting for P2/P3. Then give P1 an overlapping delta and a plan-required delta.
Verify queueing, continued active work, watcher events, and zero product actions
by P1.

**Step 3: Evaluate quality**

Run the same acceptance suite for the primary baseline, revised Herdr, and the
secondary Superpowers workload where applicable. Count failures, scope leakage,
stale receipts, identity/recovery errors, review findings, and reruns.

**Step 4: Score independently**

Write evaluator reports per locked rubric. Route every failed criterion to its
owning lane. Run at most three Plan -> Implement -> Evaluate -> Analyze cycles.
Stop only when composite and every criterion are at least 8.5, or report the
exact remaining blocker. A criterion below 7.0 is an immediate floor failure.

**Step 5: Commit reproducible benchmark artifacts**

Commit scenario, runner, methodology, and summarized results. Exclude transient
socket paths, process IDs, sessions, raw prompts, and machine-local temporary
directories.

```bash
git add benchmarks/persistent-p1 benchmarks/2026-07-29-persistent-p1.json
git commit -m "perf: benchmark persistent P1 orchestration"
```

---

### Task 8: Integrate, Install, Verify, and Publish

**Files:**

- Verify all repository files
- Sync to: `/Users/haido/.codex/skills/herdr-orchestrator`

**Step 1: Run the complete repository verification**

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/verify_contract.py
python3 scripts/verify_assets.py
git diff --check
```

Expected: all tests pass, both validators pass, and no diff errors.

**Step 2: Independent gates**

- P6 reviews the integrated diff, contract ownership, baseline fairness, and
  evidence.
- P7 repeats the live P1 distribution and lane-loss/move canary.
- P8 opens the final PNG and confirms it accurately represents the runtime.

Any finding returns to the owning lane; P5 reintegrates and reruns only impacted
plus final full checks.

**Step 3: Install the verified source**

Sync the exact committed repository state into
`/Users/haido/.codex/skills/herdr-orchestrator`, preserving no stale files.
Run the installed copy's unit suite and validators.

**Step 4: Verify repository and remote state**

```bash
git status --short --branch
git log -1 --oneline
git remote -v
```

**Step 5: Push the verified branch**

Push only after the Meta Harness reaches its target and the installed copy
passes. Report the public commit, benchmark verdict, median/p95 deltas, quality
result, and graph asset paths without claiming universal speed.
