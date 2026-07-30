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

Cold worker names are set by `herdr agent start --name <fixed-role> -- codex
--yolo`. P2-P4 use `p2_impl`, `p3_impl`, and `p4_impl`. The first prompt creates
a Codex session, and the next reconcile binds that session into the ledger.

A same-session move inside the same workspace updates only pane evidence and
preserves lane generation. A foreign workspace session is never adopted. After
three misses, recovery supersedes only the affected lane generation and starts
only that fixed slot. Runtime recovery must never close user panes.

Task text is rendered by `render_agent_status.py` beside the fixed role name.
It is never encoded into agent names.

## Controller Tick

The bounded reducer ingests inbox requests and watcher events, emits all ready
disjoint dispatch actions, and places blocked work into the ownership queue or
capacity queue. A reducer return is internal. P1 responds finally only after
terminal delivery or a real user blocker.

Watcher wake proof controls `YIELD` versus bounded `MONITOR`. Without
`watcher.wake_verified_at`, P1 keeps monitoring.

## Compact

Compact may read only state, pool, receipt, and deterministic verifier detail:

- `workspace-state.json`
- `scripts/manage_worker_pool.py`
- `scripts/write_lane_receipt.py`
- `scripts/validate_lane_receipt.py`
- `scripts/verify_contract.py`
- `scripts/verify_assets.py`
- `scripts/verify_complexity.py`

Standard-only recovery matrices and P5-P9 gates live outside the Compact path.

## Lane Brief

Every lane brief includes ROLE, GOAL, REQUIRED EVENT SKILLS,
CONTRACT / LANE / GENERATION, INPUT IDENTITY, OWNED SCOPE, PREREQUISITES,
ACCEPTANCE, TERMINAL CHECKS, RECEIPT PATH, DO NOT, and STOP / ESCALATE WHEN.
