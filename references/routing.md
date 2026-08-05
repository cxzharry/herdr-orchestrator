# Routing

P1 is controller-only. It never implements, tests, integrates, reviews,
commits, pushes, or deploys.

## Same Workspace

An ordinary current chat becomes `p1_orchestrator` only when the same Herdr
workspace lacks a live controller. P2-P9 chats forward immutable requests to the
local P1 inbox in `workspace-state.json`; they never promote themselves.

Role identity comes from `scripts/herdr_identity.py`. Pane position is evidence,
not identity.

## Worker Pool

Cold workers split from an explicit controller pane in the current workspace,
use the run root as cwd, and pass `--no-focus`. They start with `herdr agent
start <fixed-role> --kind codex --pane <id> -- --yolo`. P2-P4 use `p2_impl`,
`p3_impl`, and `p4_impl`. The first prompt creates a Codex session, and the next
reconcile binds that session into the ledger.

A same-session move inside the same workspace updates only pane evidence and
preserves lane generation. The runtime never issues pane move or close. A
foreign workspace session is never adopted. After three misses, recovery
supersedes only the affected lane generation and starts only that fixed slot.
Recovery must never close user panes.

Task text is rendered by `render_agent_status.py` beside the fixed role name.
It is never encoded into agent names.

## Controller Tick

The bounded reducer ingests inbox requests and watcher events, emits all ready
disjoint dispatch actions, and places blocked work into the ownership queue or
capacity queue. A reducer return is internal. P1 responds finally only after
terminal delivery or a real user blocker.

After contract validation, dispatch independent briefs concurrently with no
long planning prose. In both modes, prewarm P5/P6 while P2-P4 work. The reducer
may review completed lane diffs while siblings run. If an active lane
has no observable progress, redirect at 60s without observable progress and
reassign at 120s without resetting the timer. Reassignment carries explicit
ownership transfer and must prevent duplicate writes during reassignment.

Watcher wake proof controls `YIELD` versus bounded `MONITOR`. Without
`watcher.wake_verified_at`, P1 keeps monitoring.

## Compact

Compact uses one to three path-owned lanes; a single function or single file is
first-class. P5 integration and P6 independent QC are mandatory. Compact may
read only state, pool, receipt, and deterministic verifier detail:

- `workspace-state.json`
- `scripts/manage_worker_pool.py`
- `scripts/write_lane_receipt.py`
- `scripts/validate_lane_receipt.py`
- `scripts/verify_contract.py`
- `scripts/verify_assets.py`
- `scripts/verify_complexity.py`

Compact actions use prompt profile `compact-task-first-v1`. Worker briefs must
start with the owned task and acceptance. After required event skills are read
once, no generic memory, repository, or skill discovery is allowed; execute the
owned task immediately.

P5/P6 prewarm must finish required discovery before handoff. Candidate handoffs
contain only exact candidate identity, allowed paths, and exact commands; execute
the handoff immediately.

Standard-only recovery matrices and P7-P9 gates live outside the Compact path.
Standard starts applicable P7, P8, and P9 lanes concurrently against one
immutable candidate.

## Lane Brief

Every lane brief includes ROLE, GOAL, REQUIRED EVENT SKILLS,
CONTRACT / LANE / GENERATION, INPUT IDENTITY, OWNED SCOPE, PREREQUISITES,
ACCEPTANCE, TERMINAL CHECKS, RECEIPT PATH, DO NOT, and STOP / ESCALATE WHEN.
