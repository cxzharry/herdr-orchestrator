# Herdr Orchestrator Simplification Implementation Plan

> **For Herdr delivery:** REQUIRED SUB-SKILL: Use
> `herdr-orchestrator` only after this plan is approved.

**Goal:** Replace the regression-prone dynamic naming and multi-ledger runtime
with a small fixed-role, single-workspace-state controller that remains
responsive, recovers individual lanes, and beats the frozen Superpowers
performance baselines without reducing delivery quality.

**Architecture:** Build and verify a replacement candidate from stable behavior
at `2547d9b`, using one atomic `workspace-state.json`, one Herdr identity
extractor, fixed P1-P9 display roles, a pure P1 reducer, and one workspace
watcher. After independent acceptance, apply the reviewed candidate tree as a
normal forward integration commit on current `main`; never reset or
force-push public history.

**Tech Stack:** Python 3.10 standard library, Herdr CLI v0.7.5, Codex CLI,
Markdown skill contracts, `unittest`, Excalidraw/SVG/PNG assets, Git worktrees,
and SHA-addressed JSON benchmark evidence.

---

## Locked Inputs and Success Criteria

- Approved spec:
  `docs/superpowers/specs/2026-07-30-herdr-orchestrator-simplification-design.md`
- Approved spec SHA-256:
  `018b42da5222c702ed5e80010e9ce4b4fb988a52b9fa0c4082cf13d53679530d`
- Repository: `/Users/haido/herdr-orchestrator`
- Replacement behavior base:
  `2547d9b54f44e2fa994dd82511469ecd46bdfa0a`
- Forward-integration ancestry floor:
  `033a84decebfb38add7f8bc5567ae26337d5f58e`
- Rejected extension commit: `b023a4dce1b1dcde2ac5347a6ce1f0d9704b49bb`
- Frozen Superpowers Compact baseline: `152s`
- Frozen Superpowers multi-module baseline: `1009s`

The delivery is accepted only when:

1. all six workflow scenarios pass through production public helpers;
2. Compact and Standard contract validators pass;
3. P6 reports no blocking state-ownership conflict;
4. P7 records a passing isolated live canary without touching user panes;
5. Compact is verified and faster than `152s`;
6. multi-module is verified, passes the deep-immutability probe, and is faster
   than `1009s`;
7. `SKILL.md` is at most 350 words and Compact does not load Standard-only
   detail;
8. the installed skill tree exactly matches the reviewed candidate;
9. public `main` advances normally without force;
10. no user Herdr pane is closed.

## Target File Map

The replacement tree has these responsibilities:

| Path | Responsibility |
|---|---|
| `scripts/herdr_identity.py` | The only Herdr agent/session/workspace extractor and fixed role-name resolver |
| `scripts/workspace_state.py` | The only mutable ledger schema, lock, atomic write, and state mutation API |
| `scripts/manage_worker_pool.py` | Start, bind, reconcile, and replace fixed slots through the state API |
| `scripts/controller_router.py` | Claim P1 or forward worker-chat requests into the same workspace inbox |
| `scripts/controller_tick.py` | Pure bounded reducer that emits every currently ready action |
| `scripts/render_agent_status.py` | Render fixed role plus separate current-task summary |
| `scripts/run_watcher.py` | Observe live state/receipts, append events, heartbeat, and wake P1 |
| `scripts/create_control_state.py` | Thin CLI adapter that creates a workspace ledger |
| `scripts/register_lane.py` | Thin CLI adapter over lane registration |
| `scripts/set_lane_state.py` | Thin CLI adapter over generation-checked transitions |
| `scripts/write_lane_receipt.py` | Immutable terminal receipt writer |
| `scripts/validate_lane_receipt.py` | Contract/lane/generation/session/input/output validator |
| `scripts/verify_complexity.py` | Release checks for word count, forbidden modules, and duplicate helpers |
| `scripts/verify_performance.py` | Frozen-baseline digest and candidate-result gate |
| `scripts/test_workflow_scenarios.py` | Six public-helper workflow scenarios |
| `benchmarks/frozen-superpowers-v1.json` | Immutable reference values and source digests |
| `benchmarks/results/{candidate_sha}.json` | Append-only candidate evidence |

The final tree removes:

- `scripts/runtime_registry.py`
- `scripts/test_runtime_registry.py`
- `scripts/assign_agent_name.py`
- `scripts/test_assign_agent_name.py`
- `scripts/agent_naming.py`
- `scripts/test_agent_naming.py`
- `scripts/await_receipts.py`
- `scripts/test_await_receipts.py`
- `scripts/next_controller_action.py`
- `scripts/test_next_controller_action.py`
- `scripts/scheduler_state.py`
- `scripts/test_scheduler_state.py`

Do not preserve compatibility imports, legacy rename migration, task-slug name
reservations, or a second mutable pool/scheduler state file.

## Herdr Delivery Contract

```yaml
herdr_delivery:
  backend: herdr
  repository_root: /Users/haido/herdr-orchestrator
  replacement_base_sha: 2547d9b54f44e2fa994dd82511469ecd46bdfa0a
  forward_integration_ancestry_floor: 033a84decebfb38add7f8bc5567ae26337d5f58e
  approved_spec:
    path: docs/superpowers/specs/2026-07-30-herdr-orchestrator-simplification-design.md
    sha256: 018b42da5222c702ed5e80010e9ce4b4fb988a52b9fa0c4082cf13d53679530d
  plan_acceptance: pending-user-approval
  lanes:
    - lane_id: state_identity
      role: implementation
      display_role: impl
      display_slug: state
      eligible_slots: [P2, P3, P4]
      owned_paths:
        - scripts/herdr_identity.py
        - scripts/workspace_state.py
        - scripts/create_control_state.py
        - scripts/register_lane.py
        - scripts/set_lane_state.py
        - scripts/write_lane_receipt.py
        - scripts/validate_lane_receipt.py
        - scripts/test_herdr_identity.py
        - scripts/test_workspace_state.py
        - scripts/test_create_control_state.py
        - scripts/test_register_lane.py
        - scripts/test_set_lane_state.py
        - scripts/test_write_lane_receipt.py
        - scripts/test_validate_lane_receipt.py
        - benchmarks/frozen-superpowers-v1.json
        - scripts/verify_performance.py
        - scripts/test_verify_performance.py
      prerequisites: []
      dependency_wave: 1
      acceptance:
        - python3 -B -m unittest scripts.test_herdr_identity scripts.test_workspace_state scripts.test_create_control_state scripts.test_register_lane scripts.test_set_lane_state scripts.test_write_lane_receipt scripts.test_validate_lane_receipt scripts.test_verify_performance -v
      terminal_checks:
        - one mutable JSON ledger
        - one identity extractor
        - one atomic write implementation
    - lane_id: pool_recovery
      role: implementation
      display_role: impl
      display_slug: pool
      eligible_slots: [P2, P3, P4]
      owned_paths:
        - scripts/manage_worker_pool.py
        - scripts/test_manage_worker_pool.py
      prerequisites: [state_identity]
      dependency_wave: 2
      acceptance:
        - python3 -B -m unittest scripts.test_manage_worker_pool -v
      terminal_checks:
        - fixed role names and native --yolo
        - bind only after first prompt creates session
        - same-space move preserves generation
        - replacement affects only lost lane
        - no pane close command
    - lane_id: controller_watcher
      role: implementation
      display_role: impl
      display_slug: controller
      eligible_slots: [P2, P3, P4]
      owned_paths:
        - scripts/controller_router.py
        - scripts/controller_tick.py
        - scripts/render_agent_status.py
        - scripts/run_watcher.py
        - scripts/test_controller_router.py
        - scripts/test_controller_tick.py
        - scripts/test_render_agent_status.py
        - scripts/test_run_watcher.py
        - scripts/test_p1_contract.py
      prerequisites: [state_identity]
      dependency_wave: 2
      acceptance:
        - python3 -B -m unittest scripts.test_controller_router scripts.test_controller_tick scripts.test_render_agent_status scripts.test_run_watcher scripts.test_p1_contract -v
      terminal_checks:
        - worker chats only forward
        - reducer emits all ready actions
        - watcher cannot accept or dispatch
        - no early assistant final without terminal delivery or real blocker
  reviews:
    P5:
      applicable: true
      role: integration-owner-and-release-owner
      prerequisites: [state_identity, pool_recovery, controller_watcher]
      acceptance:
        - forward replacement commit on current main
        - full suite and static validators pass
        - SHA-addressed benchmark evidence exists
    P6:
      applicable: true
      role: integration-reviewer
      reason: runtime state ownership and recovery are release-critical
    P7:
      applicable: true
      role: functional-qc
      reason: six workflow scenarios and isolated live canary are mandatory
    P8:
      applicable: true
      role: design-reviewer
      reason: delivery graph and visible fixed-role status must match runtime
    P9:
      applicable: true
      role: persona-reviewer
      reason: P1 responsiveness and worker-chat forwarding are user-facing flows
  deployment:
    topology: local-skill-install-plus-public-github-main
    local_install_root: /Users/haido/.codex/skills/herdr-orchestrator
    verification: exact-tree-digest-plus-isolated-herdr-live-canary
    public_update: non-force-forward-push
  blocking_severity:
    state_ownership_conflict: release-blocking
    cross_workspace_adoption: release-blocking
    user_pane_mutation: release-blocking
    missing_watcher_wake_proof: release-blocking
    compact_at_or_above_152s: release-blocking
    multi_module_at_or_above_1009s: release-blocking
    candidate_over_10_percent_slower_than_best_herdr: warning
  required_evidence:
    - logical-lane terminal receipts
    - P5 integration receipt and tree digest
    - P6 independent review receipt
    - P7 six-scenario and live-canary receipt
    - P8 graph review receipt
    - P9 controller-persona review receipt
    - benchmarks/results/{candidate_sha}.json
```

Runtime binding may add live agent, pane, session, and lease IDs to
`control-state.json` only after this plan is approved. No such runtime identity
is part of this plan.

---

### Task 1: Create the Isolated Replacement Branch and Freeze Baselines

**Owner:** P5 creates the worktrees; P2 owns the baseline files.

**Files:**

- Create: `benchmarks/frozen-superpowers-v1.json`
- Create: `scripts/verify_performance.py`
- Create: `scripts/test_verify_performance.py`

- [ ] **Step 1: Verify the locked inputs without changing the current tree**

Run:

```bash
cd /Users/haido/herdr-orchestrator
git merge-base --is-ancestor \
  033a84decebfb38add7f8bc5567ae26337d5f58e HEAD
test "$(shasum -a 256 \
  docs/superpowers/specs/2026-07-30-herdr-orchestrator-simplification-design.md |
  awk '{print $1}')" = \
  "018b42da5222c702ed5e80010e9ce4b4fb988a52b9fa0c4082cf13d53679530d"
git status --porcelain
```

Expected: the ancestry and digest checks exit `0`, and
`git status --porcelain` is empty.

- [ ] **Step 2: Create dedicated non-destructive worktrees**

Run:

```bash
mkdir -p /Users/haido/herdr-orchestrator-worktrees
git worktree add -b simplify/replacement \
  /Users/haido/herdr-orchestrator-worktrees/replacement \
  2547d9b54f44e2fa994dd82511469ecd46bdfa0a
git worktree add -b simplify/integration \
  /Users/haido/herdr-orchestrator-worktrees/integration \
  main
```

Expected: both worktrees are created. No command resets, rebases, force-pushes,
or closes a Herdr pane.

- [ ] **Step 3: Write the failing frozen-baseline tests**

Create `scripts/test_verify_performance.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_performance import (
    PerformanceError,
    load_frozen_baseline,
    validate_candidate,
)


class PerformanceTest(unittest.TestCase):
    def test_frozen_values_and_source_digests(self):
        baseline = load_frozen_baseline(
            Path("benchmarks/frozen-superpowers-v1.json")
        )
        self.assertEqual(152, baseline["compact"]["seconds"])
        self.assertEqual(1009, baseline["multi_module"]["seconds"])

    def test_rejects_candidate_that_only_matches_baseline(self):
        baseline = {
            "compact": {"seconds": 152},
            "multi_module": {"seconds": 1009},
        }
        with self.assertRaisesRegex(PerformanceError, "compact"):
            validate_candidate(
                baseline,
                {
                    "compact": {"seconds": 152, "verified": True},
                    "multi_module": {
                        "seconds": 900,
                        "verified": True,
                        "deep_immutability": True,
                    },
                },
                [],
            )

    def test_warns_when_slower_than_best_herdr(self):
        result = validate_candidate(
            {
                "compact": {"seconds": 152},
                "multi_module": {"seconds": 1009},
            },
            {
                "compact": {"seconds": 120, "verified": True},
                "multi_module": {
                    "seconds": 850,
                    "verified": True,
                    "deep_immutability": True,
                },
            },
            [{"compact": {"seconds": 100}, "multi_module": {"seconds": 800}}],
        )
        self.assertEqual(
            ["compact >10% slower than best Herdr",
             "multi_module >10% slower than best Herdr"],
            result["warnings"],
        )
```

Run:

```bash
python3 -B -m unittest scripts.test_verify_performance -v
```

Expected: FAIL because `scripts.verify_performance` does not exist.

- [ ] **Step 4: Record the immutable baseline and minimal validator**

Create `benchmarks/frozen-superpowers-v1.json`:

```json
{
  "schema_version": "herdr-frozen-superpowers/v1",
  "rebaseline_policy": "explicit-user-request-only",
  "compact": {
    "seconds": 152,
    "source": "benchmarks/2026-07-28-compact-runtime.json",
    "source_sha256": "6acc1d0437b51b362a818f58f17c90eca8f9ff632dcbbd754d4b1060adc0549b"
  },
  "multi_module": {
    "seconds": 1009,
    "source": "benchmarks/2026-07-28-multi-module.json",
    "source_sha256": "880ee46ec808c985bd544510409137e88a930e72d297f2a36b1721c4e5c39f88",
    "required_quality": ["shared_acceptance", "deep_immutability"]
  }
}
```

Implement these public functions in `scripts/verify_performance.py`:

```python
class PerformanceError(RuntimeError):
    pass


def load_frozen_baseline(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "herdr-frozen-superpowers/v1":
        raise PerformanceError("unsupported frozen baseline")
    return value


def validate_candidate(baseline, candidate, previous):
    failures = []
    if not candidate["compact"]["verified"]:
        failures.append("compact acceptance failed")
    if candidate["compact"]["seconds"] >= baseline["compact"]["seconds"]:
        failures.append("compact did not beat frozen baseline")
    multi = candidate["multi_module"]
    if not multi["verified"] or not multi["deep_immutability"]:
        failures.append("multi_module quality failed")
    if multi["seconds"] >= baseline["multi_module"]["seconds"]:
        failures.append("multi_module did not beat frozen baseline")
    if failures:
        raise PerformanceError("; ".join(failures))

    warnings = []
    for key in ("compact", "multi_module"):
        samples = [item[key]["seconds"] for item in previous if key in item]
        if samples and candidate[key]["seconds"] > min(samples) * 1.10:
            warnings.append(f"{key} >10% slower than best Herdr")
    return {"status": "pass", "warnings": warnings}
```

Add imports, CLI parsing, SHA-addressed output-path validation, and source-file
SHA-256 verification in the same file. The CLI must refuse an output filename
that differs from `{git-rev-parse-HEAD}.json` and must never overwrite an
existing result.

- [ ] **Step 5: Run focused tests and commit**

Run:

```bash
python3 -B -m unittest scripts.test_verify_performance -v
git add benchmarks/frozen-superpowers-v1.json \
  scripts/verify_performance.py scripts/test_verify_performance.py
git commit -m "test: freeze Superpowers performance baselines"
```

Expected: tests PASS and one focused commit exists on the replacement branch.

---

### Task 2: Introduce One Identity Extractor and One Workspace Ledger

**Owner:** `state_identity` lane.

**Files:**

- Create: `scripts/herdr_identity.py`
- Create: `scripts/workspace_state.py`
- Create: `scripts/test_herdr_identity.py`
- Create: `scripts/test_workspace_state.py`
- Modify: `scripts/create_control_state.py`
- Modify: `scripts/register_lane.py`
- Modify: `scripts/set_lane_state.py`
- Modify: `scripts/write_lane_receipt.py`
- Modify: `scripts/validate_lane_receipt.py`
- Modify corresponding `scripts/test_*.py`

- [ ] **Step 1: Write RED identity tests**

Create `scripts/test_herdr_identity.py` with these exact invariants:

```python
import unittest
from scripts.herdr_identity import agent_identity, fixed_role_name


class IdentityTest(unittest.TestCase):
    def test_extracts_nested_codex_session_once(self):
        self.assertEqual(
            {
                "name": "p2_impl",
                "pane_id": "w6:p2",
                "workspace_id": "w6",
                "terminal_id": "terminal-2",
                "session_id": "session-2",
                "status": "working",
            },
            agent_identity({
                "name": "p2_impl",
                "pane_id": "w6:p2",
                "workspace_id": "w6",
                "terminal_id": "terminal-2",
                "agent_session": {"value": "session-2"},
                "agent_status": "working",
            }),
        )

    def test_fixed_names_never_include_task_text(self):
        self.assertEqual("p1_orchestrator", fixed_role_name("P1", "w6", set()))
        self.assertEqual("p4_impl", fixed_role_name("P4", "w6", set()))
        self.assertEqual(
            "p4_impl_w6",
            fixed_role_name("P4", "w6", {"p4_impl"}),
        )
```

Run:

```bash
python3 -B -m unittest scripts.test_herdr_identity -v
```

Expected: FAIL because the module does not exist.

- [ ] **Step 2: Implement the only identity module**

Create `scripts/herdr_identity.py` around this fixed contract:

```python
ROLE_NAMES = {
    "P1": "p1_orchestrator",
    "P2": "p2_impl",
    "P3": "p3_impl",
    "P4": "p4_impl",
    "P5": "p5_integration",
    "P6": "p6_review",
    "P7": "p7_qc",
    "P8": "p8_design",
    "P9": "p9_persona",
}


def agent_identity(agent):
    nested = agent.get("agent_session") or {}
    session = nested.get("value")
    return {
        "name": agent.get("name") or "",
        "pane_id": agent.get("pane_id"),
        "workspace_id": agent.get("workspace_id"),
        "terminal_id": agent.get("terminal_id"),
        "session_id": str(session) if session else None,
        "status": agent.get("agent_status"),
    }


def fixed_role_name(slot, workspace_id, occupied):
    base = ROLE_NAMES[slot]
    return base if base not in occupied else f"{base}_{workspace_id}"
```

No other module may parse `agent_session`, derive a workspace from a pane, or
construct role names.

- [ ] **Step 3: Write RED ledger tests**

Create `scripts/test_workspace_state.py` and cover:

```python
def test_initial_state_has_one_complete_schema(self):
    state = initial_state(
        "w6",
        controller={"role_name": "p1_orchestrator",
                    "session_id": "controller-session"},
    )
    self.assertEqual(
        {
            "schema_version", "workspace_id", "revision", "controller",
            "slots", "run", "lanes", "requests", "request_order", "inbox",
            "queues", "watcher", "events", "event_cursor",
        },
        set(state),
    )
    self.assertEqual("p2_impl", state["slots"]["P2"]["role_name"])


def test_state_changes_increment_revision_once(self):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "workspace-state.json"
        create_state(
            path,
            "w6",
            controller={"role_name": "p1_orchestrator",
                        "session_id": "controller-session"},
        )
        before = load_state(path)["revision"]
        mutate_state(path, lambda value: value["inbox"].append({"id": "x"}))
        self.assertEqual(before + 1, load_state(path)["revision"])


def test_stale_generation_cannot_transition_lane(self):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "workspace-state.json"
        create_state(path, "w6")
        register_lane(path, {
            "lane_id": "state_identity",
            "generation": 2,
            "state": "ACTIVE",
            "session_id": "worker-session",
        })
        with self.assertRaisesRegex(StateError, "generation"):
            transition_lane(
                path, "state_identity", 1, "ACCEPTED"
            )
```

Import `tempfile`, `unittest`, `Path`, `StateError`, `create_state`,
`initial_state`, `load_state`, `mutate_state`, `register_lane`, and
`transition_lane` at the top of the test module.

Run:

```bash
python3 -B -m unittest scripts.test_workspace_state -v
```

Expected: FAIL because `workspace_state.py` does not exist.

- [ ] **Step 4: Implement the single ledger and atomic mutation boundary**

Create `scripts/workspace_state.py` with one state schema:

```python
SCHEMA = "herdr-workspace-state/v1"
IMPLEMENTATION_SLOTS = ("P2", "P3", "P4")
TERMINAL_LANE_STATES = {
    "ACCEPTED", "FINDING", "BLOCKED", "LOST", "SUPERSEDED"
}


def initial_state(workspace_id, controller=None):
    return {
        "schema_version": SCHEMA,
        "workspace_id": workspace_id,
        "revision": 0,
        "controller": controller or {},
        "slots": {
            slot: {
                "role_name": ROLE_NAMES[slot],
                "session_id": None,
                "pane_id": None,
                "status": "COLD",
                "misses": 0,
            }
            for slot in ROLE_NAMES
        },
        "run": {},
        "lanes": {},
        "requests": {},
        "request_order": [],
        "inbox": [],
        "queues": {"ownership": [], "capacity": []},
        "watcher": {
            "watcher_id": None,
            "heartbeat_at": None,
            "wake_verified_at": None,
        },
        "events": [],
        "event_cursor": 0,
    }
```

Implement only these mutation APIs: `load_state`, `create_state`,
`mutate_state`, `append_inbox`, `append_observation`,
`apply_controller_tick`, `register_lane`, and `transition_lane`. Each accepts
the `Path` to the same workspace ledger as its first argument.

`mutate_state` is the only function that uses `fcntl.flock`, `tempfile.mkstemp`,
`json.dump`, and `os.replace`. It increments `revision` once if and only if the
canonical JSON changes. All CLI adapters call this module; none write JSON
directly.

- [ ] **Step 5: Convert state and receipt adapters**

Update the existing CLI adapters so:

- `create_control_state.py` creates `workspace-state.json`;
- `register_lane.py` and `set_lane_state.py` call generation-checked state APIs;
- `write_lane_receipt.py` writes immutable receipts with
  `contract_id`, `lane_id`, `generation`, `session_id`, `input_identity`,
  `output_artifact`, and `verification`;
- `validate_lane_receipt.py` does not validate pane or display name as identity;
- a valid receipt already persisted remains valid after pane movement.

The validity key must be:

```python
def receipt_identity(receipt):
    return {
        "contract_id": receipt["contract_id"],
        "lane_id": receipt["lane_id"],
        "generation": receipt["generation"],
        "session_id": receipt["session_id"],
        "input_identity": receipt["input_identity"],
        "output_artifact": receipt["output_artifact"],
    }
```

- [ ] **Step 6: Run focused tests and commit**

Run:

```bash
python3 -B -m unittest \
  scripts.test_herdr_identity scripts.test_workspace_state \
  scripts.test_create_control_state scripts.test_register_lane \
  scripts.test_set_lane_state scripts.test_write_lane_receipt \
  scripts.test_validate_lane_receipt -v
git add scripts/herdr_identity.py scripts/workspace_state.py \
  scripts/create_control_state.py scripts/register_lane.py \
  scripts/set_lane_state.py scripts/write_lane_receipt.py \
  scripts/validate_lane_receipt.py scripts/test_herdr_identity.py \
  scripts/test_workspace_state.py scripts/test_create_control_state.py \
  scripts/test_register_lane.py scripts/test_set_lane_state.py \
  scripts/test_write_lane_receipt.py scripts/test_validate_lane_receipt.py
git commit -m "refactor: unify Herdr workspace state"
```

Expected: all focused tests PASS.

---

### Task 3: Simplify the Worker Pool to Fixed Roles and Local Recovery

**Owner:** `pool_recovery` lane after Task 2 receipt is accepted.

**Files:**

- Modify: `scripts/manage_worker_pool.py`
- Modify: `scripts/test_manage_worker_pool.py`

- [ ] **Step 1: Replace naming tests with fixed-role lifecycle tests**

Add test cases using the public `WorkerPool.ensure()` and `reconcile()` APIs:

```python
def test_cold_start_uses_fixed_name_yolo_model_and_effort(self):
    pool.ensure(["P2"])
    self.assertEqual(
        [
            "herdr", "agent", "start", "--name", "p2_impl",
            "--", "codex", "--yolo", "-m", "gpt-5.5",
            "-c", "model_reasoning_effort=high",
        ],
        client.started[0],
    )


def test_cold_worker_binds_session_only_after_first_prompt(self):
    pool.ensure(["P2"])
    self.assertIsNone(load_state(path)["slots"]["P2"]["session_id"])
    client.agents = [live("P2", session_id="new-session")]
    pool.reconcile()
    self.assertEqual(
        "new-session", load_state(path)["slots"]["P2"]["session_id"]
    )


def test_same_workspace_move_preserves_generation(self):
    seed_bound_slot(path, "P2", "session-2", "w6:p2", generation=3)
    client.agents = [live("P2", "session-2", pane="w6:p9", workspace="w6")]
    pool.reconcile()
    state = load_state(path)
    self.assertEqual("w6:p9", state["slots"]["P2"]["pane_id"])
    self.assertEqual(3, state["lanes"]["lane-a"]["generation"])


def test_three_misses_replace_only_lost_lane(self):
    seed_three_busy_slots(path)
    client.agents = [live("P3"), live("P4")]
    for _ in range(3):
        pool.reconcile()
    state = load_state(path)
    self.assertEqual("SUPERSEDED", state["lanes"]["lane-p2"]["state"])
    self.assertEqual("ACTIVE", state["lanes"]["lane-p3"]["state"])
    self.assertEqual("ACTIVE", state["lanes"]["lane-p4"]["state"])
    self.assertEqual(["P2"], client.replacement_slots)


def test_foreign_workspace_session_is_never_adopted(self):
    seed_bound_slot(path, "P2", "session-2", "w6:p2")
    client.agents = [
        live("P2", "session-2", pane="w7:p2", workspace="w7")
    ]
    for _ in range(3):
        pool.reconcile()
    self.assertNotEqual(
        "w7:p2", load_state(path)["slots"]["P2"]["pane_id"]
    )
    self.assertEqual([], client.prompts_to_workspace("w7"))


def test_valid_receipt_wins_when_worker_disappears(self):
    seed_bound_slot(path, "P2", "session-2", "w6:p2", generation=2)
    persist_valid_receipt(path, lane="lane-a", generation=2)
    client.agents = []
    for _ in range(3):
        pool.reconcile()
    state = load_state(path)
    self.assertEqual("ACCEPTED", state["lanes"]["lane-a"]["state"])
    self.assertEqual([], client.replacement_slots)


def test_full_herdr_restart_discards_live_sessions_only(self):
    seed_bound_slot(path, "P2", "old-session", "w6:p2", generation=2)
    persist_matching_git_artifact(path, lane="lane-a", generation=2)
    pool.reconcile(restart_detected=True)
    state = load_state(path)
    self.assertIsNone(state["slots"]["P2"]["session_id"])
    self.assertEqual("REUSABLE", state["lanes"]["lane-a"]["artifact_state"])
    self.assertNotEqual("old-session", state["run"].get("controller_session_id"))
```

Also assert the fake client never receives `pane close`, `agent move`, or
pre-prompt `agent rename`. A valid receipt wins if it was persisted before the
worker disappeared; do not start a replacement for that accepted lane.

- [ ] **Step 2: Run RED pool tests**

Run:

```bash
python3 -B -m unittest scripts.test_manage_worker_pool -v
```

Expected: FAIL because the old pool requires dynamic names and separate state.

- [ ] **Step 3: Reduce `manage_worker_pool.py` to one state client**

Keep a focused `WorkerPool` with this public surface:

```python
class WorkerPool:
    def __init__(self, client, state_path, workspace_id):
        self.client = client
        self.state_path = Path(state_path)
        self.workspace_id = workspace_id

    def ensure(self, slots):
        live = [agent_identity(item) for item in self.client.list_agents()]
        for slot in slots:
            if not self._local_slot_live(slot, live):
                self._start(slot, occupied={item["name"] for item in live})
        return self.reconcile(live)

    def reconcile(self, live=None, restart_detected=False):
        observations = live or [
            agent_identity(item) for item in self.client.list_agents()
        ]
        return apply_pool_observations(
            self.state_path,
            self.workspace_id,
            observations,
            self._start,
            restart_detected=restart_detected,
        )
```

The start command is fixed:

```python
def start_command(slot, workspace_id, occupied):
    name = fixed_role_name(slot, workspace_id, occupied)
    model = "gpt-5.6-sol" if slot == "P1" else "gpt-5.5"
    effort = "xhigh" if slot == "P1" else "high"
    return [
        "herdr", "agent", "start", "--name", name,
        "--", "codex", "--yolo", "-m", model,
        "-c", f"model_reasoning_effort={effort}",
    ]
```

Do not add a retry registry. Launch failure leaves the fixed slot `COLD` or
`START_FAILED` in the workspace ledger so the next tick retries the same slot.
On a full Herdr restart, clear all old live controller/worker session bindings,
create a new pool/run identity, and reuse only receipts or Git artifacts whose
locked input identity still matches.

- [ ] **Step 4: Run focused tests and commit**

Run:

```bash
python3 -B -m unittest scripts.test_manage_worker_pool -v
git add scripts/manage_worker_pool.py scripts/test_manage_worker_pool.py
git commit -m "refactor: use fixed Herdr worker roles"
```

Expected: tests PASS, and `rg 'rename|quarantine|task_slug|runtime_registry'
scripts/manage_worker_pool.py` returns no runtime naming path.

---

### Task 4: Make P1 a Pure Multi-Action Reducer

**Owner:** `controller_watcher` lane after Task 2 receipt is accepted.

**Files:**

- Modify: `scripts/controller_router.py`
- Create: `scripts/controller_tick.py`
- Create: `scripts/render_agent_status.py`
- Modify: `scripts/test_controller_router.py`
- Create: `scripts/test_controller_tick.py`
- Create: `scripts/test_render_agent_status.py`
- Modify: `scripts/test_p1_contract.py`

- [ ] **Step 1: Write RED routing and reducer tests**

Lock these flows:

```python
def request(request_id, paths):
    return {
        "request_id": request_id,
        "summary": request_id,
        "affected_paths": paths,
        "dependencies": [],
    }


def state_with_free_slots(*slots):
    state = initial_state(
        "w6",
        controller={"role_name": "p1_orchestrator",
                    "session_id": "controller-session"},
    )
    for slot in slots:
        state["slots"][slot]["status"] = "IDLE"
        state["slots"][slot]["session_id"] = f"{slot.lower()}-session"
    return state


def busy_state(heartbeat_at=None, wake_verified_at=None):
    state = state_with_free_slots("P2", "P3", "P4")
    for slot in ("P2", "P3", "P4"):
        state["slots"][slot]["status"] = "BUSY"
    state["run"] = {"status": "ACTIVE"}
    state["watcher"]["heartbeat_at"] = heartbeat_at
    state["watcher"]["wake_verified_at"] = wake_verified_at
    return state


def test_ordinary_chat_claims_p1_when_workspace_has_no_controller(self):
    current_chat = {
        "name": "",
        "pane_id": "w6:p1",
        "workspace_id": "w6",
        "terminal_id": "terminal-1",
        "agent_session": {"value": "controller-session"},
        "agent_status": "working",
    }
    result = decide_controller_action(current_chat, None, workspace_id="w6")
    self.assertEqual("CLAIM_P1", result["action"])


def test_worker_chat_forwards_and_never_promotes(self):
    controller = {
        "name": "p1_orchestrator",
        "pane_id": "w6:p1",
        "workspace_id": "w6",
        "agent_session": {"value": "controller-session"},
        "agent_status": "idle",
    }
    for slot in ("P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"):
        worker = {
            "name": ROLE_NAMES[slot],
            "pane_id": f"w6:{slot.lower()}",
            "workspace_id": "w6",
            "agent_session": {"value": f"{slot.lower()}-session"},
            "agent_status": "working",
        }
        result = decide_controller_action(
            worker, controller, workspace_id="w6"
        )
        self.assertEqual("FORWARD", result["action"])


def test_tick_emits_all_ready_work_in_one_return(self):
    result = controller_tick(
        state_with_free_slots("P2", "P3", "P4"),
        requests=[
            request("a", ["a/**"]),
            request("b", ["b/**"]),
            request("c", ["c/**"]),
        ],
        events=[],
        live_agents=[],
        now=100,
    )
    self.assertEqual(
        [
            ("DISPATCH", "P2"),
            ("DISPATCH", "P3"),
            ("DISPATCH", "P4"),
        ],
        [(item["kind"], item["slot"]) for item in result["actions"]],
    )


def test_nonterminal_reducer_return_is_not_assistant_final(self):
    result = controller_tick(
        busy_state(), requests=[], events=[], live_agents=[], now=100
    )
    self.assertFalse(result["assistant_may_finalize"])
    self.assertEqual("MONITOR", result["actions"][0]["kind"])


def test_missing_wake_proof_forces_bounded_monitoring(self):
    state = busy_state(
        heartbeat_at=99,
        wake_verified_at=None,
    )
    result = controller_tick(
        state, requests=[], events=[], live_agents=[], now=100
    )
    self.assertEqual("MONITOR", result["actions"][0]["kind"])
    self.assertFalse(result["may_yield"])


def test_status_separates_fixed_role_from_current_task(self):
    state = state_with_free_slots("P2")
    state["slots"]["P2"]["status"] = "BUSY"
    state["slots"]["P2"]["task_summary"] = "unify workspace ledger"
    self.assertEqual(
        "P2 | p2_impl | BUSY | unify workspace ledger",
        render_agent_status(state)[0],
    )
```

Import `ROLE_NAMES`, `initial_state`, `decide_controller_action`, and
`controller_tick` and `render_agent_status` from their production modules. The
tests must use the literal fixtures above rather than pane-position inference.

Run:

```bash
python3 -B -m unittest scripts.test_controller_router \
  scripts.test_controller_tick scripts.test_render_agent_status \
  scripts.test_p1_contract -v
```

Expected: FAIL against one-action routing and premature final behavior.

- [ ] **Step 2: Simplify controller claiming and forwarding**

`controller_router.py` must:

1. use `agent_identity()` from `herdr_identity.py`;
2. scope controller discovery and inbox strictly to `workspace_id`;
3. claim the current ordinary chat as fixed `p1_orchestrator` when no live P1
   exists;
4. forward P2-P9 requests by appending an immutable envelope to the same
   workspace ledger;
5. signal the live P1 only after persisting the envelope;
6. never infer role from pane position.

The action contract is:

```python
{"action": "CONTINUE", "workspace_id": "w6"}
{"action": "CLAIM_P1", "workspace_id": "w6"}
{"action": "FORWARD", "workspace_id": "w6", "request_id": "request-a"}
{"action": "BLOCK", "reason": "BLOCKED_NO_LOCAL_CONTROLLER"}
```

- [ ] **Step 3: Implement the pure controller tick**

Create `scripts/controller_tick.py`:

```python
def controller_tick(state, requests, events, live_agents, now):
    next_state = copy.deepcopy(state)
    reconcile_live(next_state, live_agents)
    ingest_requests(next_state, requests)
    ingest_events(next_state, events)
    actions = emit_ready_actions(next_state)

    terminal = delivery_terminal(next_state)
    wake_ready = watcher_wake_proven(next_state, now)
    if not actions and not terminal:
        actions = [{
            "kind": "YIELD" if wake_ready else "MONITOR",
            "timeout_seconds": 30,
        }]
    return {
        "state": next_state,
        "actions": actions,
        "may_yield": bool(not terminal and wake_ready),
        "assistant_may_finalize": terminal or real_user_blocker(next_state),
    }
```

`emit_ready_actions()` loops until no additional action is ready. It dispatches
all disjoint requests that fit current capacity, leaves overlapping work in
`queues.ownership`, leaves excess disjoint work in `queues.capacity`, and emits
gate actions only after dependencies have accepted receipts.

P1 does not run any product command. `scripts/test_p1_contract.py` must reject
P1 ownership of implementation, tests, integration, review, commit, push, or
deploy in `SKILL.md`, routing docs, and graph text.

- [ ] **Step 4: Render role and task as separate fields**

Create `scripts/render_agent_status.py`:

```python
def render_agent_status(state):
    rows = []
    for slot in sorted(state["slots"]):
        value = state["slots"][slot]
        task = value.get("task_summary") or "-"
        rows.append(
            f"{slot} | {value['role_name']} | {value['status']} | {task}"
        )
    return rows
```

The renderer is read-only and may not persist state or rename an agent.

- [ ] **Step 5: Run focused tests and commit**

Run:

```bash
python3 -B -m unittest scripts.test_controller_router \
  scripts.test_controller_tick scripts.test_render_agent_status \
  scripts.test_p1_contract -v
git add scripts/controller_router.py scripts/controller_tick.py \
  scripts/render_agent_status.py scripts/test_controller_router.py \
  scripts/test_controller_tick.py scripts/test_render_agent_status.py \
  scripts/test_p1_contract.py
git commit -m "refactor: make P1 a pure responsive reducer"
```

Expected: all focused tests PASS.

---

### Task 5: Replace Receipt Waiting with One Workspace Watcher

**Owner:** `controller_watcher` lane.

**Files:**

- Modify: `scripts/run_watcher.py`
- Modify: `scripts/test_run_watcher.py`

- [ ] **Step 1: Write RED watcher-boundary tests**

Add:

```python
def test_watcher_only_appends_observations(self):
    before = load_state(path)
    run_once(path, adapter, now=100)
    after = load_state(path)
    self.assertEqual(before["lanes"], after["lanes"])
    self.assertEqual(before["queues"], after["queues"])
    self.assertTrue(after["events"])
    self.assertEqual(100, after["watcher"]["heartbeat_at"])


def test_one_watcher_per_workspace_controller_lifecycle(self):
    first = acquire_watcher(path, "watcher-a", controller_session="p1-a")
    second = acquire_watcher(path, "watcher-b", controller_session="p1-a")
    self.assertTrue(first)
    self.assertFalse(second)


def test_actionable_event_is_persisted_before_p1_signal(self):
    run_once(path, adapter, now=100)
    self.assertTrue(load_state(path)["events"])
    self.assertEqual(["p1_orchestrator"], adapter.signals)
```

Run:

```bash
python3 -B -m unittest scripts.test_run_watcher -v
```

Expected: FAIL where the old watcher mutates lane state or duplicates state
write logic.

- [ ] **Step 2: Implement a read-observe-signal watcher**

Keep only these capabilities:

```python
def observe_once(state, live_agents, receipt_paths, now):
    return {
        "heartbeat_at": now,
        "events": live_agent_events(state, live_agents)
        + receipt_events(state, receipt_paths),
    }


def run_once(state_path, adapter, now):
    state = load_state(state_path)
    observation = observe_once(
        state,
        adapter.list_agents(),
        expected_receipt_paths(state),
        now,
    )
    for event in observation["events"]:
        append_observation(state_path, event)
    record_heartbeat(state_path, now)
    if observation["events"]:
        adapter.signal_agent(state["controller"]["role_name"], "HERDR_EVENT")
    return observation
```

The watcher may not call `transition_lane`, assign a slot, increment a
generation, accept a receipt, or dispatch a prompt. Event IDs are hashes of
workspace, kind, lane, generation, session, and artifact identity so repeated
polls are idempotent.

- [ ] **Step 3: Prove the wake path**

On startup, the watcher writes its heartbeat, appends a synthetic
`WAKE_PROBE`, signals P1, and waits for the reducer to advance `event_cursor`.
Only then set `watcher.wake_verified_at`. If the cursor does not advance within
the bounded probe window, keep `wake_verified_at = null`; P1 must monitor
instead of yielding.

- [ ] **Step 4: Run focused tests and commit**

Run:

```bash
python3 -B -m unittest scripts.test_run_watcher \
  scripts.test_controller_tick -v
git add scripts/run_watcher.py scripts/test_run_watcher.py
git commit -m "refactor: observe delivery with one workspace watcher"
```

Expected: tests PASS.

---

### Task 6: Add End-to-End Workflow Scenarios Through Public Helpers

**Owner:** P5 adds integration scenarios after accepting Tasks 2-5 receipts.

**Files:**

- Create: `scripts/test_workflow_scenarios.py`
- Modify only if a scenario exposes a defect:
  `scripts/herdr_identity.py`, `scripts/workspace_state.py`,
  `scripts/manage_worker_pool.py`, `scripts/controller_router.py`,
  `scripts/controller_tick.py`, or `scripts/run_watcher.py`

- [ ] **Step 1: Build one public-helper fake Herdr adapter**

Use `ControllerRouter`, `WorkerPool`, `controller_tick`, and `run_once`; do not
call private helpers. The fake adapter records starts, prompts, signals, moves,
and forbidden mutations:

```python
class ScenarioHerdr:
    def __init__(self, workspace_id):
        self.workspace_id = workspace_id
        self.agents = []
        self.started = []
        self.prompts = []
        self.signals = []
        self.closed = []

    def list_agents(self):
        return copy.deepcopy(self.agents)

    def start_agent(self, command):
        self.started.append(command)

    def prompt_agent(self, target, capsule):
        self.prompts.append((target, capsule))

    def signal_agent(self, target, value):
        self.signals.append((target, value))

    def close_pane(self, pane):
        self.closed.append(pane)
        raise AssertionError("runtime must never close a user pane")
```

- [ ] **Step 2: Add the six locked scenarios**

Name the tests exactly:

```text
test_cold_p2_p4_first_prompt_then_session_bind
test_disjoint_request_dispatches_while_workers_busy
test_same_workspace_move_preserves_lane_and_generation
test_closed_worker_replaces_only_lost_lane
test_foreign_workspace_agent_is_never_adopted
test_missing_watcher_proof_prevents_early_final
```

Each test creates a real temporary `workspace-state.json`, invokes the public
helpers in production order, asserts state plus emitted actions, and asserts
`adapter.closed == []`.

- [ ] **Step 3: Run scenarios before the full suite**

Run:

```bash
python3 -B -m unittest scripts.test_workflow_scenarios -v
python3 -B -m unittest discover -s scripts -p 'test_*.py' -v
```

Expected: the six scenarios and full discovery PASS. If a scenario fails,
apply the smallest correction only in the exposed production helper, add a
focused regression assertion, and rerun both commands.

- [ ] **Step 4: Commit**

Run:

```bash
git add scripts/test_workflow_scenarios.py scripts/
git commit -m "test: cover Herdr delivery workflows end to end"
```

Before committing, confirm `git diff --cached --name-only` contains no
unrelated docs, benchmark results, or user workspace artifacts.

---

### Task 7: Delete Superseded Runtime Paths and Enforce Complexity

**Owner:** P5 integration owner.

**Files:**

- Delete the twelve files listed in **Target File Map**
- Create: `scripts/verify_complexity.py`
- Create: `scripts/test_verify_complexity.py`
- Modify: `scripts/verify_contract.py`
- Modify: `scripts/test_p1_contract.py`

- [ ] **Step 1: Write RED complexity tests**

Create `scripts/test_verify_complexity.py`:

```python
import unittest
from pathlib import Path
from scripts.verify_complexity import verify


class ComplexityTest(unittest.TestCase):
    def test_replacement_has_one_state_and_identity_owner(self):
        report = verify(Path("."))
        self.assertEqual([], report["errors"])

    def test_skill_is_at_most_350_words(self):
        report = verify(Path("."))
        self.assertLessEqual(report["skill_words"], 350)
```

`verify()` must report an error for:

- any superseded file still present;
- more than one occurrence of `agent_session` parsing outside
  `herdr_identity.py`;
- `fcntl.flock`, `tempfile.mkstemp`, or `os.replace` used for mutable state
  outside `workspace_state.py`;
- `runtime-registry`, `task_slug`, `rename before prompt`, or
  `legacy rename migration` in active runtime docs;
- `await_receipts` referenced by P1 routing;
- Compact routing linking Standard recovery/review references;
- `SKILL.md` over 350 words.

- [ ] **Step 2: Run the RED validator**

Run:

```bash
python3 -B -m unittest scripts.test_verify_complexity -v
```

Expected: FAIL while superseded modules and duplicate helpers still exist.

- [ ] **Step 3: Remove superseded modules**

Run:

```bash
git rm scripts/runtime_registry.py scripts/test_runtime_registry.py \
  scripts/assign_agent_name.py scripts/test_assign_agent_name.py \
  scripts/agent_naming.py scripts/test_agent_naming.py \
  scripts/await_receipts.py scripts/test_await_receipts.py \
  scripts/next_controller_action.py scripts/test_next_controller_action.py \
  scripts/scheduler_state.py scripts/test_scheduler_state.py
```

Update active imports to the replacement modules. Do not add shims.

- [ ] **Step 4: Implement and run complexity checks**

Run:

```bash
python3 -B -m unittest scripts.test_verify_complexity -v
python3 -B scripts/verify_complexity.py
python3 -B -m unittest discover -s scripts -p 'test_*.py' -v
```

Expected: PASS; the CLI prints JSON with `"status": "pass"` and
`"skill_words"` at or below `350`.

- [ ] **Step 5: Commit**

Run:

```bash
git add scripts
git commit -m "refactor: remove superseded Herdr runtime paths"
```

---

### Task 8: Rewrite the Compact Contract and Delivery Graph

**Owner:** P5 integration owner; P8 performs read-only visual review.

**Files:**

- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `references/routing.md`
- Modify: `references/delivery-flow.md`
- Modify: `references/high-assurance.md`
- Modify: `references/review-deploy.md`
- Modify: `references/plan-contract.md`
- Modify: `assets/delivery-flow.excalidraw`
- Modify: `assets/delivery-flow.svg`
- Modify: `assets/delivery-flow.png`
- Modify: `assets/manifest.json`
- Modify: `scripts/render_assets.py`
- Modify: `scripts/verify_assets.py`
- Modify: `scripts/verify_contract.py`

- [ ] **Step 1: Reduce `SKILL.md` to the routing kernel**

The file must contain only:

1. approved-plan and `HERDR_ENV=1` preconditions;
2. same-workspace P1 claim/worker forwarding;
3. Compact vs Standard predicate;
4. fixed role roster;
5. one controller-tick command;
6. links to detailed Standard references.

It must explicitly say:

```markdown
P1 is controller-only. It never implements, tests, integrates, reviews,
commits, pushes, or deploys. A reducer return is internal: respond finally only
after terminal delivery or a real user blocker.
```

Run:

```bash
python3 - <<'PY'
from pathlib import Path
text = Path("SKILL.md").read_text()
print(len(text.split()))
PY
```

Expected: output is at most `350`.

- [ ] **Step 2: Rewrite routing around fixed slots and one ledger**

`references/routing.md` must state:

- current ordinary chat becomes P1 if the workspace lacks a live controller;
- P2-P9 forward requests to local P1;
- cold worker name is set in `herdr agent start`;
- every new worker command contains `codex --yolo`;
- first prompt creates a session and the next reconcile binds it;
- same-session same-workspace move updates only pane evidence;
- three misses supersede only the affected lane generation;
- foreign workspace is never adopted;
- watcher proof controls yield vs bounded monitor;
- task text is rendered by `render_agent_status.py`, not encoded in names.

Compact may link only the state, pool, receipt, and deterministic verifier
sections. Standard-only recovery matrices and P5-P9 gates remain in
`high-assurance.md` and `review-deploy.md`.

- [ ] **Step 3: Update the README without universal performance claims**

Keep the frozen numbers and add:

```markdown
The Superpowers baselines are frozen reference values. After each skill
change, only the Herdr candidate is rerun and stored under its Git SHA.
Herdr is released only when the candidate beats 152s on Compact and 1009s on
the multi-module scenario while passing the same quality gates.
```

Explain fixed role names, visible task summaries, one workspace ledger, P1
responsiveness, same-space isolation, and that panes remain open.

- [ ] **Step 4: Redraw the engineering graph**

The graph must show this exact flow:

```text
Approved plan
  -> P1 claim or same-workspace forward
  -> atomic controller tick
       -> P2/P3/P4 fixed warm implementation slots
       -> ownership queue / capacity queue
  -> immutable receipts
  -> Compact verifier OR Standard P5 integration
  -> P6 review -> conditional P7/P8/P9
  -> P5 install/push/deploy

Herdr live state -> workspace watcher -> event queue -> P1 wake
workspace-state.json -> controller tick
```

Label P1 `p1_orchestrator` and each P2-P9 fixed role. Put task summary beside a
slot, not inside its name. Show `same workspace only` as a boundary and
`never close user panes` in recovery.

- [ ] **Step 5: Render and validate docs/assets**

Run:

```bash
python3 -B scripts/render_assets.py
python3 -B scripts/render_assets.py --check assets/delivery-flow.png
python3 -B scripts/verify_assets.py
python3 -B scripts/verify_contract.py
python3 /Users/haido/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```

Expected: all commands PASS.

- [ ] **Step 6: P8 visually reviews the PNG**

P8 opens `assets/delivery-flow.png` and records PASS only if:

- text is legible at normal zoom;
- P1 is visibly controller-only;
- fixed role plus separate task summary is obvious;
- Compact and Standard paths are distinct;
- watcher event direction is one-way into P1;
- foreign-workspace adoption and pane closure are not shown.

Route a visual finding to P5, rerender, rerun Step 5, and request a new P8
receipt.

- [ ] **Step 7: Commit**

Run:

```bash
git add SKILL.md README.md references assets scripts/render_assets.py \
  scripts/verify_assets.py scripts/verify_contract.py
git commit -m "docs: align Herdr skill and delivery graph"
```

---

### Task 9: Produce the Forward Replacement Integration Commit

**Owner:** P5.

**Files:** The reviewed replacement tree applied to the integration worktree.

- [ ] **Step 1: Verify every implementation receipt**

For each logical lane, validate:

```bash
python3 -B scripts/validate_lane_receipt.py \
  --control-state "$HERDR_RUN_ROOT/workspace-state.json" \
  --receipt "$HERDR_RUN_ROOT/receipts/${lane_id}-g${generation}.json"
```

Expected: JSON status `valid`. Do not consume unaccepted worker changes.

- [ ] **Step 2: Create a candidate tree commit on the replacement branch**

Run full checks:

```bash
python3 -B -m unittest discover -s scripts -p 'test_*.py' -v
python3 -B scripts/verify_contract.py
python3 -B scripts/verify_assets.py
python3 -B scripts/render_assets.py --check assets/delivery-flow.png
python3 -B scripts/verify_complexity.py
python3 /Users/haido/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
git status --porcelain
```

Expected: every command PASS and status is clean after candidate commits.

- [ ] **Step 3: Apply the reviewed tree as a normal forward change**

From `/Users/haido/herdr-orchestrator-worktrees/integration`, copy only the
reviewed tracked-tree delta from the replacement candidate, then stage it.
Use Git plumbing to avoid checkout/reset:

```bash
candidate_sha="$(git -C \
  /Users/haido/herdr-orchestrator-worktrees/replacement rev-parse HEAD)"
git diff --binary \
  2547d9b54f44e2fa994dd82511469ecd46bdfa0a.."$candidate_sha" \
  > /tmp/herdr-simplification.patch
git apply --index --3way /tmp/herdr-simplification.patch
git status --short
```

Resolve only conflicts caused by changes after `2547d9b`, preserving the
approved spec and plan. Explicitly remove current-only superseded modules from
the index. Never use `git reset`, `git rebase`, or a force option.

- [ ] **Step 4: Verify the staged integration tree**

Run the full commands from Step 2 in the integration worktree, then inspect:

```bash
git diff --cached --stat
git diff --cached --check
git diff --cached --name-status
```

Expected: no whitespace errors, no unrelated workspace files, and the spec plus
plan remain present.

- [ ] **Step 5: Commit the forward replacement**

Run:

```bash
git commit -m "refactor: simplify Herdr orchestration runtime"
```

Expected: the new commit has the plan-approved `main` tip as its first parent
and `033a84decebfb38add7f8bc5567ae26337d5f58e` in its ancestry, while its
reviewed runtime behavior derives from the `2547d9b` replacement candidate.

---

### Task 10: Run Independent Review and Workflow QC

**Owners:** P6 code review, P7 functional QC, P9 controller-persona review.

**Files:** Read-only unless P5 receives and fixes a finding.

- [ ] **Step 1: P6 reviews state ownership and the integrated diff**

P6 must inspect:

```bash
git diff --stat 033a84decebfb38add7f8bc5567ae26337d5f58e..HEAD
git diff 033a84decebfb38add7f8bc5567ae26337d5f58e..HEAD -- \
  scripts SKILL.md references
rg -n 'agent_session|fcntl\\.flock|tempfile\\.mkstemp|os\\.replace|runtime_registry|task_slug|await_receipts' \
  scripts SKILL.md references
```

P6 records a blocking finding for duplicated identity extraction, multiple
mutable ledgers, watcher-owned transitions, P1 product work, cross-workspace
adoption, or a live-name validity key.

- [ ] **Step 2: P7 runs all six deterministic scenarios**

Run:

```bash
python3 -B -m unittest scripts.test_workflow_scenarios -v
```

Expected: six named tests PASS.

- [ ] **Step 3: P7 runs an isolated live Herdr canary**

Create a new dedicated Herdr test session/workspace. Start fixed P2-P4 with
native `--yolo`, dispatch three harmless disjoint fixture edits, move one test
pane inside the test workspace, close one test worker only, and verify:

- first-prompt session binding succeeds;
- moved lane preserves generation;
- closed test worker alone is replaced after three misses;
- healthy test siblings continue;
- a request arriving while workers are busy is classified and queued/dispatched
  immediately by P1;
- no existing user workspace or pane is addressed.

Record the test workspace identity and event/receipt paths in the P7 receipt.
Do not record those live IDs in this plan or reuse them for release.

- [ ] **Step 4: P9 reviews P1 interaction behavior**

P9 uses the isolated test workspace to confirm:

- an ordinary chat becomes P1 when none exists;
- chatting to P2-P9 forwards to the existing P1;
- P1 accepts a new request while prior lanes remain active;
- task summaries make active work understandable without dynamic names;
- P1 does not claim completion on a nonterminal reducer return;
- a missing wake proof keeps P1 monitoring.

- [ ] **Step 5: Route findings narrowly**

Each finding names the violated criterion, evidence, owning lane, and required
rerun. P5 applies the smallest fix, reruns the focused failing test plus full
suite, and requests only impacted review receipts again.

---

### Task 11: Rerun Herdr Candidates Against the Frozen Baseline

**Owner:** P7 executes; P5 validates and records.

**Files:**

- Create: `benchmarks/results/{integration_sha}.json`

- [ ] **Step 1: Do not rerun Superpowers**

Verify the frozen file and its source snapshots:

```bash
python3 -B scripts/verify_performance.py --verify-baseline
```

Expected: PASS with Compact `152` and multi-module `1009`. No Superpowers
process is started.

- [ ] **Step 2: Run the Compact candidate**

Use the existing locked three-disjoint-edits input and shared deterministic
acceptance. Run with a warm fixed P2-P4 pool and Compact verifier. Record wall
clock, acceptance, scope cleanliness, rework loops, and candidate SHA.

Required result:

```json
{
  "compact": {
    "seconds": 151,
    "verified": true,
    "scope_clean": true
  }
}
```

`151` illustrates the strict upper bound; record the measured integer. Any
value `>= 152`, failed acceptance, or dirty scope blocks release.

- [ ] **Step 3: Run the multi-module candidate**

Use the existing locked multi-module canary input, shared acceptance, and deep
immutability probe. Record:

```json
{
  "multi_module": {
    "seconds": 1008,
    "verified": true,
    "deep_immutability": true
  }
}
```

`1008` illustrates the strict upper bound; record the measured integer. Any
value `>= 1009`, failed shared acceptance, or failed deep-immutability probe
blocks release.

- [ ] **Step 4: Write a new SHA-addressed result**

Set:

```bash
candidate_sha="$(git rev-parse HEAD)"
result_path="benchmarks/results/${candidate_sha}.json"
test ! -e "$result_path"
```

The result includes baseline digest, candidate SHA, scenario inputs, timings,
quality outcomes, rework, raw evidence paths, and warnings versus the best
comparable Herdr result. Validate:

```bash
python3 -B scripts/verify_performance.py \
  --candidate "$result_path" \
  --previous-glob 'benchmarks/results/*.json'
```

Expected: PASS. A >10% slowdown versus the best prior Herdr result is a warning
that must be reported, not hidden.

- [ ] **Step 5: Commit benchmark evidence**

Run:

```bash
git add "$result_path"
git commit -m "bench: record simplified Herdr candidate"
```

---

### Task 12: Install the Reviewed Tree and Push Public Main

**Owner:** P5 after P6-P9 and performance acceptance.

**Files:** local installed skill and public Git branch.

- [ ] **Step 1: Re-run the release gate at final HEAD**

Run:

```bash
python3 -B -m unittest discover -s scripts -p 'test_*.py' -v
python3 -B scripts/verify_contract.py
python3 -B scripts/verify_assets.py
python3 -B scripts/render_assets.py --check assets/delivery-flow.png
python3 -B scripts/verify_complexity.py
result_path="$(
  git diff-tree --no-commit-id --name-only -r HEAD |
  rg '^benchmarks/results/[0-9a-f]{40}\.json$'
)"
test -n "$result_path"
python3 -B scripts/verify_performance.py \
  --candidate "$result_path" \
  --previous-glob 'benchmarks/results/*.json'
python3 /Users/haido/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
git diff --check
```

Expected: all commands PASS. If the benchmark evidence commit changes the SHA
addressing rule, the validator must accept an artifact whose recorded
`candidate_sha` is the immediately preceding runtime commit.

- [ ] **Step 2: Install by exact tracked-tree copy**

Use a temporary directory and replace only the skill install target. Preserve
no stale files from the old install:

```bash
install_tmp="$(mktemp -d)"
git archive HEAD | tar -x -C "$install_tmp"
rsync -a --delete \
  --exclude '.git' \
  "$install_tmp/" /Users/haido/.codex/skills/herdr-orchestrator/
```

Do not close or restart any existing Herdr pane.

- [ ] **Step 3: Prove repository/install equality**

Run:

```bash
repo_digest="$(
  git ls-files -z |
  LC_ALL=C sort -z |
  xargs -0 shasum -a 256 |
  shasum -a 256 |
  awk '{print $1}'
)"
install_digest="$(
  git ls-files -z |
  LC_ALL=C sort -z |
  while IFS= read -r -d '' path; do
    shasum -a 256 "/Users/haido/.codex/skills/herdr-orchestrator/$path"
  done |
  shasum -a 256 |
  awk '{print $1}'
)"
test "$repo_digest" = "$install_digest"
```

Expected: equality test exits `0`.

- [ ] **Step 4: Fast-forward local main and push without force**

After verifying the integration worktree is based on the approved current
main, update the primary checkout by normal fast-forward and push:

```bash
git -C /Users/haido/herdr-orchestrator merge --ff-only simplify/integration
git -C /Users/haido/herdr-orchestrator push origin main
```

Expected: push succeeds without `--force`; `git status --short --branch` shows
local `main` aligned with `origin/main`.

- [ ] **Step 5: Record the release handoff**

P5 reports:

- final public SHA;
- installed-tree digest;
- six-scenario and isolated-canary status;
- P6-P9 receipt paths;
- Compact and multi-module measured seconds versus `152s` and `1009s`;
- any >10% Herdr regression warning;
- confirmation that no user pane was closed.

Do not claim completion if any required receipt, performance gate, or tree
equality check is missing.
