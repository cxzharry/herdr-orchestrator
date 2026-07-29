# Dynamic Pane Role Names Implementation Plan

> **For Herdr delivery:** REQUIRED SUB-SKILL: Use
> `herdr-orchestrator` only after this plan is approved.

**Goal:** Replace opaque `hdr_p1` through `hdr_p9` live names with bounded
role-and-task names such as `p2_impl_auth` while preserving stable slot,
session, lane, receipt, pane-move recovery, and independent concurrent-space
orchestration.

**Architecture:** Add one pure naming module as the only formatter/parser.
Controller routing, warm-pool management, assignment, and recovery use stable
controller scope plus slot and Codex session identity, and treat the current
Herdr name as a mutable display/target handle. A dedicated assignment helper
performs rename-before-prompt and atomically publishes the verified live name
to control state. Inboxes, pools, integration/review ownership, and recovery
remain isolated by controller scope even when panes move between workspaces.

**Tech Stack:** Python 3.10 standard library, `unittest`, Herdr 0.7.5 CLI,
JSON control state, Markdown, Excalidraw/SVG/PNG deterministic assets.

---

## File Structure

### New files

- `scripts/agent_naming.py`: pure slot parsing, slug normalization, bounded
  name formatting, collision suffixing, and stable identity helpers.
- `scripts/test_agent_naming.py`: formatter/parser boundary tests.
- `scripts/runtime_registry.py`: socket-global locked controller, live-name,
  session-lease, and legacy-claim registry.
- `scripts/test_runtime_registry.py`: simultaneous allocation, cross-scope
  lease, crash-resume, and legacy-claim tests.
- `scripts/assign_agent_name.py`: live rename-before-prompt command and atomic
  control-state publication.
- `scripts/test_assign_agent_name.py`: assignment, collision, stale-state, and
  verification tests.
- `scripts/render_agent_status.py`: bounded one-read P1-P9 status output.
- `scripts/test_render_agent_status.py`: ordered role/name/status tests.
- `scripts/next_controller_action.py`: pure scoped gate decision after
  compaction/resume.
- `scripts/test_next_controller_action.py`: Standard, Compact, and
  cross-scope boundary regressions.

### Modified runtime files

- `scripts/controller_router.py`: recognize legacy and dynamic P1-P9 names,
  promote independent controller scopes, target the recorded scoped
  controller, and exclude mutable display names from request identity.
- `scripts/test_controller_router.py`: dynamic controller/worker, legacy
  compatibility, forwarding, and rename-stable request-ID tests.
- `scripts/manage_worker_pool.py`: bootstrap `p2_worker_ready` through
  `p4_worker_ready`, isolate concurrent pools by controller scope, reconcile by
  session, migrate legacy names, and stop indexing durable pool state by
  mutable names.
- `scripts/test_manage_worker_pool.py`: dynamic bootstrap, migration, reset,
  pane move, missing-worker, and same-session reuse tests.
- `scripts/scheduler_state.py`: preserve approved `display_role` and
  `display_slug`, controller scope, and name reservations on dispatch.
- `scripts/test_scheduler_state.py`: scope, reservation, and display metadata
  propagation tests.
- `scripts/create_control_state.py` and `scripts/register_lane.py`: normalize
  new and legacy logical naming metadata without breaking v1 inputs.
- Their tests: new, legacy, on-demand, and cross-scope state regressions.
- `scripts/write_lane_receipt.py` and `scripts/validate_lane_receipt.py`:
  freeze receipt identity to the verified dispatch name.
- Their tests: migration, drift, move, and accepted legacy receipt regressions.
- `scripts/await_receipts.py`: report dynamic-name drift independently from
  pane movement and preserve expected display identity.
- `scripts/test_await_receipts.py`: move-with-name and name-drift tests.
- `scripts/run_watcher.py`: emit immutable `LANE_NAME_DRIFT` events.
- `scripts/test_run_watcher.py`: watcher event and dynamic P1 signal tests.

### Modified contract and documentation files

- `SKILL.md`: require role assignment before every prompt and document the
  dynamic naming lifecycle.
- `README.md`: document visible names, migration, and examples; remove the
  hard-coded script-test count that becomes stale whenever tests are added.
- `references/plan-contract.md`: add logical `display_slug`; keep live names
  forbidden in approved plans.
- `references/routing.md`: add rename-before-prompt and name-drift routing.
- `references/delivery-flow.md`: document the live-name legend.
- `scripts/verify_contract.py`: require naming helper, assignment helper, and
  dynamic-name contract markers.
- `scripts/test_p1_contract.py`: lock P1's new visible name and unchanged
  orchestration-only boundary.

### Modified graph files

- `assets/delivery-flow.excalidraw`: add a concise live-name-format note.
- `assets/delivery-flow.svg`: deterministic render source with the same note.
- `assets/delivery-flow.png`: regenerated artifact.
- `assets/manifest.json`: updated source/render/hash bindings.
- `scripts/verify_assets.py`: require the new note without changing topology.

## Meta-Harness Execution Lock

**Gate:** PROCEED — this is a multi-file workflow improvement with identity,
recovery, concurrency, documentation, and visual-asset failure modes.

**Intent:** IMPROVE

**Mode:** Auto recommended — parallel Herdr lanes after approval.

The implementation loop is limited to three iterations. Before implementation,
write the run artifacts under
`/Users/haido/.codex/meta-harness/dynamic-pane-role-names-20260729/`, reusing
this plan and the approved design spec as the Phase 1 sources. Only the two
skill RED/GREEN evidence files explicitly owned by Task 6 are committed to the
repository.

Lock this rubric before the first edit:

| Criterion | Pass evidence | Minimum |
| --- | --- | --- |
| Identity and recovery correctness | Unit suites plus live pane-move, name-drift, legacy migration, and stable request-ID canaries | 8/10 |
| P1 distribution and legacy-feature continuity | P1 accepts new deltas while lanes work; one workspace may run independent P1 scopes while another workspace is a separate pool; Compact/Standard routing, warm pool, receipts, review applicability, integration ownership, deployment, and public release regressions all pass | 8/10 |
| Naming flexibility | Arbitrary approved roles/tasks, bounded truncation, deterministic collisions, concurrent same-numbered slots, P5 phase changes, legacy names, pane moves, and closed-lane replacement work without binding plans to live IDs | 8/10 |
| Dispatch speed and hot-path size | No rename starts a Codex process; scheduler benchmark stays within the locked threshold; root `SKILL.md` is at most 330 words and 2,350 bytes | 8/10 |
| Contract and release completeness | Full tests, contract/assets validators, original-detail graph review, installed-copy verification, exact public SHA | 8/10 |

Target composite is 8/10 and no criterion may score below 8. Each evaluator
score needs command output or live evidence. A failed iteration must classify
the failure as plan, implementation, rubric, or environment and record what
the next iteration must not retry.

The pre-change root-skill baseline is 349 words and 2,418 bytes. New naming
detail belongs in selective references and executable helpers; the root skill
keeps only the dispatch invariant. This makes the hot path smaller, not merely
below the existing 350-word validator cap.

The controller-boundary pressure case is mandatory: after artificial context
compaction, an applicable Standard run must route verification to P5 and
applicable QC/design to P7/P8. Any controller-pane edit, test, integration,
browser, or deployment command is an immediate floor failure.

### Parallelization Strategy

**Implementation parallelism:** Parallel lanes

**Reason:** the naming core is the only shared prerequisite; controller/pool
and assignment/recovery then own disjoint files, followed by one contract and
asset lane.

- **Can parallelize:** yes
- **Implementation lanes:** Task 1 runs first; Tasks 2-3 share one
  controller/pool owner while Tasks 4-5 share one assignment/recovery owner;
  Task 6 starts after both are accepted.
- **Sequential dependencies:** naming core before runtime consumers; runtime
  consumers before contract/assets; all accepted worker SHAs before P5
  integration, live canary, installation, and release.
- **Verification:** focused RED/GREEN checks per lane, then the complete suite,
  live Herdr canary, P6 integration review, P7 QC, and P8 graph review.
- **Recommended Phase 3 Agent Split Gate input:** Spawn — ownership is disjoint
  and the two wave-2 lanes can run concurrently without edit conflicts.

## Task 1: Pure Dynamic Naming Contract

**Files:**

- Create: `scripts/agent_naming.py`
- Create: `scripts/test_agent_naming.py`
- Create: `scripts/runtime_registry.py`
- Create: `scripts/test_runtime_registry.py`

- [ ] **Step 1: Write failing parser and formatter tests**

Create `scripts/test_agent_naming.py`:

```python
import unittest

from scripts.agent_naming import (
    NamingError,
    canonical_display_role,
    format_agent_name,
    slot_from_agent_name,
    slot_from_lane_id,
    stable_agent_identity,
)


class AgentNamingTests(unittest.TestCase):
    def test_parses_legacy_and_dynamic_names_to_the_same_slot(self):
        self.assertEqual(slot_from_agent_name("hdr_p2"), "P2")
        self.assertEqual(slot_from_agent_name("p2_worker_ready"), "P2")
        self.assertEqual(slot_from_agent_name("p2_impl_auth"), "P2")

    def test_formats_role_and_task_as_a_bounded_herdr_name(self):
        value = format_agent_name(
            "P8",
            "UI Review",
            "Checkout accessibility and responsive behavior",
        )
        self.assertTrue(value.startswith("p8_ui_review_"))
        self.assertLessEqual(len(value), 32)
        self.assertRegex(value, r"^[a-z][a-z0-9_-]{0,31}$")

    def test_formats_controller_and_ready_workers(self):
        self.assertEqual(
            format_agent_name("P1", "orchestrator"),
            "p1_orchestrator",
        )
        self.assertEqual(
            format_agent_name("P3", "worker", "ready"),
            "p3_worker_ready",
        )
        self.assertEqual(
            format_agent_name("P5", "integration_owner"),
            "p5_integration_owner",
        )
        self.assertEqual(
            format_agent_name("P6", "integration_review"),
            "p6_integration_review",
        )

    def test_collision_suffix_is_deterministic(self):
        occupied = {"p2_impl_auth"}
        first = format_agent_name(
            "P2",
            "impl",
            "auth",
            occupied=occupied,
            collision_key="lane-auth",
        )
        second = format_agent_name(
            "P2",
            "impl",
            "auth",
            occupied=occupied,
            collision_key="lane-auth",
        )
        self.assertEqual(first, second)
        self.assertNotEqual(first, "p2_impl_auth")
        self.assertLessEqual(len(first), 32)

    def test_collision_without_lane_identity_fails_closed(self):
        with self.assertRaisesRegex(NamingError, "collision_key"):
            format_agent_name(
                "P2",
                "impl",
                "auth",
                occupied={"p2_impl_auth"},
            )

    def test_collision_suffix_extends_until_the_name_is_unique(self):
        first = format_agent_name(
            "P2",
            "impl",
            "auth",
            occupied={"p2_impl_auth"},
            collision_key="lane-auth",
        )
        second = format_agent_name(
            "P2",
            "impl",
            "auth",
            occupied={"p2_impl_auth", first},
            collision_key="lane-auth",
        )
        self.assertNotEqual(first, second)
        self.assertLessEqual(len(second), 32)

    def test_long_task_truncates_only_the_task_segment(self):
        value = format_agent_name(
            "P9",
            "persona",
            "administrator_checkout_approval_journey",
        )
        self.assertTrue(value.startswith("p9_persona_"))
        self.assertLessEqual(len(value), 32)

    def test_derives_only_canonical_legacy_metadata(self):
        self.assertEqual(slot_from_lane_id("p8"), "P8")
        self.assertIsNone(slot_from_lane_id("checkout-ui"))
        self.assertEqual(
            canonical_display_role("P5", "integration-owner"),
            "integration_owner",
        )
        self.assertEqual(
            canonical_display_role("P8", "designer"),
            "ui_review",
        )

    def test_request_identity_uses_slot_and_session_not_display_name(self):
        first = stable_agent_identity("p2_impl_auth", "session-p2")
        renamed = stable_agent_identity("p2_impl_schema", "session-p2")
        legacy = stable_agent_identity("hdr_p2", "session-p2")
        self.assertEqual(first, renamed)
        self.assertEqual(first, legacy)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest scripts.test_agent_naming -v
```

Expected: `ERROR` with
`ModuleNotFoundError: No module named 'scripts.agent_naming'`.

- [ ] **Step 3: Implement the pure naming module**

Create `scripts/agent_naming.py`:

```python
#!/usr/bin/env python3
"""Pure visible-name helpers for Herdr P1-P9 agents."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Collection


MAX_AGENT_NAME = 32
_SLOT = re.compile(r"^(?:hdr_)?p([1-9])(?:_|$)")
_SEPARATORS = re.compile(r"[^a-z0-9]+")
_CANONICAL_ROLES = {
    "orchestrator": "orchestrator",
    "implementation": "impl",
    "worker": "impl",
    "integration_owner": "integration_owner",
    "integration_reviewer": "integration_review",
    "deployment": "deploy",
    "qc": "qc",
    "designer": "ui_review",
    "persona": "persona",
}


class NamingError(ValueError):
    pass


def normalize_slot(value: str) -> str:
    slot = str(value).upper()
    if not re.fullmatch(r"P[1-9]", slot):
        raise NamingError(f"invalid Herdr slot: {value}")
    return slot


def normalize_slug(value: str, *, fallback: str | None = None) -> str:
    slug = _SEPARATORS.sub("_", str(value).lower()).strip("_")
    if slug:
        return slug
    if fallback is not None:
        return fallback
    raise NamingError("name slug is empty")


def slot_from_agent_name(name: str | None) -> str | None:
    match = _SLOT.match(name or "")
    return f"P{match.group(1)}" if match else None


def slot_from_lane_id(lane_id: str | None) -> str | None:
    match = re.fullmatch(r"[pP]([1-9])", lane_id or "")
    return f"P{match.group(1)}" if match else None


def canonical_display_role(slot: str | None, role: str) -> str:
    del slot
    normalized = normalize_slug(role)
    return _CANONICAL_ROLES.get(normalized, normalized)


def format_agent_name(
    slot: str,
    role: str,
    task: str | None = None,
    *,
    occupied: Collection[str] = (),
    collision_key: str | None = None,
) -> str:
    prefix = normalize_slot(slot).lower()
    role_slug = normalize_slug(role)
    role_prefix = f"{prefix}_{role_slug}"
    if len(role_prefix) > MAX_AGENT_NAME:
        raise NamingError("slot and role do not fit Herdr's name limit")
    task_slug = (
        normalize_slug(task, fallback="task")
        if task is not None
        else None
    )
    candidate = role_prefix
    if task_slug is not None:
        task_budget = MAX_AGENT_NAME - len(role_prefix) - 1
        if task_budget > 0:
            candidate = f"{role_prefix}_{task_slug[:task_budget].rstrip('_')}"
    if candidate not in occupied:
        return candidate
    if not collision_key:
        raise NamingError("collision_key is required for an occupied name")
    digest = hashlib.sha256(collision_key.encode()).hexdigest()
    max_suffix = MAX_AGENT_NAME - len(role_prefix) - 1
    for suffix_length in range(4, min(len(digest), max_suffix) + 1, 2):
        suffix = digest[:suffix_length]
        head_budget = MAX_AGENT_NAME - len(suffix) - 1
        head = candidate[:head_budget].rstrip("_")
        if not head.startswith(role_prefix):
            break
        suffixed = f"{head}_{suffix}"
        if suffixed not in occupied:
            return suffixed
    raise NamingError("cannot produce a unique bounded Herdr name")


def stable_agent_identity(
    name: str | None,
    session_id: str | None,
) -> dict[str, str | None]:
    return {
        "slot": slot_from_agent_name(name),
        "session_id": session_id,
    }
```

- [ ] **Step 4: Run the focused test to verify GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest scripts.test_agent_naming -v
```

Expected: nine tests, `OK`.

- [ ] **Step 5: Add a RED/GREEN socket-global runtime registry**

Write `scripts/test_runtime_registry.py` before implementation. Use two Python
threads released by one barrier to simulate separate spaces allocating the
same P1 and P2 candidates concurrently. Require:

- distinct unique names;
- one stable registered name per controller scope even after another name is
  freed;
- one live session leased to at most one controller scope/lane;
- deterministic same-token reservation resume after interruption;
- a different token cannot steal a pending reservation;
- only the recorded legacy P1 session can claim the old global inbox and v1
  pool; a second scope fails closed.

Confirm RED with missing module, then create `scripts/runtime_registry.py`.
Store one registry at
`<runtime_root>/<socket_key>/runtime-registry.json`, protected by an adjacent
`fcntl` lock. Provide atomic reserve/finalize/release operations for:

```text
controller_scope -> controller session + stable visible name
visible name -> controller scope + session + slot + reservation token
live session -> controller scope + contract + lane + generation
legacy global resources -> recorded legacy controller session + claimed scope
```

Name selection occurs while holding this registry lock and considers both live
Herdr names and pending registry reservations. External Herdr rename/start
happens after reservation; finalization verifies session/name under the same
token. Crashed deterministic reservations are resumable. Do not hold the
registry lock during a Herdr CLI call.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  scripts.test_runtime_registry -v
```

Expected: concurrent allocation and lease tests report `OK`.

- [ ] **Step 6: Commit the naming and registry core**

```bash
git add \
  scripts/agent_naming.py \
  scripts/test_agent_naming.py \
  scripts/runtime_registry.py \
  scripts/test_runtime_registry.py
git commit -m "feat: define dynamic Herdr agent names"
```

## Task 2: Scoped Dynamic Controllers and Stable Request Identity

**Depends on:** Task 1

**Files:**

- Modify: `scripts/controller_router.py`
- Modify: `scripts/test_controller_router.py`

- [ ] **Step 1: Write failing dynamic-role regression tests**

Add imports and tests to `scripts/test_controller_router.py`:

```python
class DynamicControllerDecisionTests(unittest.TestCase):
    def test_dynamic_worker_forwards_to_dynamic_controller(self):
        current = agent("p2_impl_auth", "w1:p2", "session-worker")
        controller = agent(
            "p1_orchestrator",
            "w1:p1",
            "session-p1",
            status="idle",
        )

        result = decide_controller_action(current, controller)

        self.assertEqual(result["action"], "FORWARD")
        self.assertEqual(result["controller_pane_id"], "w1:p1")

    def test_legacy_worker_still_forwards_during_migration(self):
        current = agent("hdr_p7", "w1:p7", "session-worker")
        controller = agent("p1_orchestrator", "w1:p1", "session-p1")

        result = decide_controller_action(current, controller)

        self.assertEqual(result["action"], "FORWARD")


class DynamicControllerRouterTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_promotion_renames_controller_to_visible_role(self):
        current = agent("", "w1:p2", "session-new", terminal="term-new")
        client = FakeClient(
            [agent("", "w1:p2", "session-new", terminal="term-new")]
        )
        router = ControllerRouter(client, self.root, "sock-a")

        result = router.promote(current)

        self.assertEqual(result["controller"]["name"], "p1_orchestrator")
        self.assertIn(
            ("rename_agent", "w1:p2", "p1_orchestrator"),
            client.calls,
        )

    def test_first_tick_migrates_legacy_controller_without_new_session(self):
        current = agent(
            "hdr_p1",
            "w1:p7",
            "session-p1",
            terminal="term-p1",
            status="working",
        )
        client = FakeClient([current])
        router = ControllerRouter(client, self.root, "sock-a")

        result = router.ensure_controller_name(current)

        self.assertEqual(result["name"], "p1_orchestrator")
        self.assertEqual(result["session_id"], "session-p1")
        self.assertIn(
            ("rename_agent", "w1:p7", "p1_orchestrator"),
            client.calls,
        )

    def test_request_id_survives_role_and_task_rename(self):
        controller = agent(
            "p1_orchestrator",
            "w1:p1",
            "session-p1",
            status="idle",
        )
        router = ControllerRouter(
            client=FakeClient([controller]),
            inbox_root=self.root,
            socket_key="sock-a",
        )
        request = {"text": "same user delta"}

        first = router.forward_request(
            agent("p2_impl_auth", "w1:p2", "session-worker"),
            controller,
            request,
        )
        renamed = router.forward_request(
            agent("p2_impl_schema", "w2:p8", "session-worker"),
            controller,
            request,
        )

        self.assertEqual(first["request_id"], renamed["request_id"])
```

Keep the existing legacy, status-change, and pane-move request-ID regressions.

- [ ] **Step 2: Run the controller tests to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest scripts.test_controller_router -v
```

Expected failures:

- dynamic P2 is treated as `BLOCKED_NO_CONTROLLER`;
- promotion still renames to `hdr_p1`;
- task rename changes the request ID.

- [ ] **Step 3: Add the workspace-bound RED regression**

Add a test that creates two unnamed main-chat agents in the same workspace and a
third agent in another workspace on the same fake Herdr socket. Release all
promotion threads from one barrier and require:

- the same-workspace agents get distinct controller scopes derived from their
  stable sessions;
- their unique P1 live names both parse as slot P1;
- the other workspace gets a separate pool, inbox, watcher queue, and registry;
- a P2 request carrying scope A forwards only to controller A even while
  controller B is idle;
- no controller adopts, renames, resets, prompts, receipts, or signals across
  the workspace boundary.

- [ ] **Step 4: Replace fixed-name decisions with scoped slot decisions**

In `scripts/controller_router.py`, replace fixed-name constants and identity
logic with:

```python
try:
    from scripts.agent_naming import (
        format_agent_name,
        slot_from_agent_name,
        stable_agent_identity,
    )
except ModuleNotFoundError:
    from agent_naming import (
        format_agent_name,
        slot_from_agent_name,
        stable_agent_identity,
    )


WORKER_SLOTS = {f"P{index}" for index in range(2, 10)}


def controller_scope_id(session: str) -> str:
    return hashlib.sha256(session.encode()).hexdigest()[:8]


def controller_name(
    scope: str,
    occupied: set[str],
) -> str:
    return format_agent_name(
        "P1",
        "orchestrator",
        occupied=occupied,
        collision_key=scope,
    )
```

Use Task 1's lock-protected `RuntimeRegistry`. Controller entries are keyed by
`controller_scope` and contain the stable controller session plus current
mutable name/pane/workspace handles. Never select a controller by “nearest
workspace” or by the first P1-shaped name.

Inside `decide_controller_action`, use:

```python
current_slot = slot_from_agent_name(current_name)

if current_slot == "P1":
    if not live_controller:
        return {"action": "CONTINUE", **current}
    controller = compact_identity(live_controller)
    if controller["session_id"] != current["session_id"]:
        return {"action": "BLOCK", "reason": "BLOCKED_ROLE_CONFLICT"}
    return {"action": "CONTINUE", **current}

if current_slot in WORKER_SLOTS:
    if not live_controller:
        return {"action": "BLOCK", "reason": "BLOCKED_NO_CONTROLLER"}
    controller = compact_identity(live_controller)
    return {
        "action": "FORWARD",
        "controller_session_id": controller["session_id"],
        "controller_pane_id": controller["pane_id"],
    }
```

In `promote`, derive scope from the current main-chat session, reserve a unique
P1 name through `RuntimeRegistry.reserve_name`, rename, verify the same
session, then finalize the same token. Two promotions released by a test
barrier must both succeed with distinct names:

```python
reservation = self.registry.reserve_name(
    controller_scope=scope,
    session_id=before["session_id"],
    slot="P1",
    candidate=format_agent_name("P1", "orchestrator"),
    collision_key=scope,
    live_names={agent.get("name") for agent in self.client.list_agents()},
)
self.client.rename_agent(before["pane_id"], reservation["name"])
live = [
    compact_identity(agent)
    for agent in self.client.list_agents()
    if session_id(agent) == before["session_id"]
]
self.registry.finalize_name(
    reservation["token"],
    pane_id=live[0]["pane_id"],
    workspace_id=live[0]["workspace_id"],
)
```

Add `ensure_controller_name`. It accepts either legacy `hdr_p1` or dynamic P1,
renames only the legacy handle, then re-reads by stable session and verifies
that pane, terminal, and session still identify the same controller. It must
work while P1 reports `working`; a display rename is not a reset or ownership
transfer. The first scheduler tick calls this method before processing inbox or
watcher events.

```python
def ensure_controller_name(
    self,
    current_agent: dict[str, Any],
    *,
    controller_scope: str | None = None,
) -> dict[str, Any]:
    before = compact_identity(current_agent)
    if slot_from_agent_name(before["name"]) != "P1":
        raise RouterError("current agent is not the controller")
    scope = controller_scope or controller_scope_id(before["session_id"])
    registered = self.registry.get(scope)
    if registered:
        expected_name = registered["name"]
    else:
        occupied = {
            agent.get("name")
            for agent in self.client.list_agents()
            if session_id(agent) != before["session_id"] and agent.get("name")
        }
        expected_name = controller_name(scope, occupied)
    if before["name"] == expected_name:
        self.registry.bind(scope, before)
        return before
    if before["name"] != "hdr_p1" and not registered:
        raise RouterError("unsupported controller display name")
    self.client.rename_agent(before["pane_id"], expected_name)
    matches = [
        compact_identity(agent)
        for agent in self.client.list_agents()
        if session_id(agent) == before["session_id"]
    ]
    if len(matches) != 1 or matches[0]["name"] != expected_name:
        raise RouterError("controller rename was not verified")
    after = matches[0]
    if after["terminal_id"] != before["terminal_id"]:
        raise RouterError("controller terminal changed during migration")
    self.registry.bind(scope, after)
    return after
```

Treat the snippet's unregistered `expected_name` computation as
`RuntimeRegistry.reserve_name(...)`; finalize it only after live verification.
For an existing scope, always reuse `registered["name"]` even if a shorter
base name later becomes free. Never downgrade a surviving suffixed P1 or reject
it merely because occupancy changed.

In `forward_request`, signal the verified live controller name:

```python
if target["status"] in SETTLED_STATUSES and not already_queued:
    self.client.signal_agent(target["name"], request_id)
    return {"action": "FORWARDED", "request_id": request_id}
```

Write envelopes under
`<inbox_root>/<socket_key>/<controller_scope>/p1-inbox/` and include
`controller_scope` in request identity. A named P2-P9 lane obtains this scope
from its control-state/pool lease; an unnamed main chat promotes into a new
scope even when other P1 agents exist.

Add a legacy-inbox test with two queued request files under the old
`<socket_key>/p1-inbox`. The `hdr_p1` session recorded by the old state claims
that resource through `RuntimeRegistry`, atomically moves the files into its
scoped inbox without changing request IDs/content, and writes a migration
marker. A second controller scope must neither see nor move them. An
interrupted migration resumes idempotently.

Replace `immutable_agent_identity` with:

```python
def immutable_agent_identity(identity: dict[str, Any]) -> dict[str, Any]:
    return stable_agent_identity(
        identity.get("name"),
        identity.get("session_id"),
    )
```

- [ ] **Step 5: Run focused controller tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest scripts.test_controller_router -v
```

Expected: all controller-router tests, including status, pane move, and display
rename identity regressions, report `OK`.

- [ ] **Step 6: Commit controller routing**

```bash
git add scripts/controller_router.py scripts/test_controller_router.py
git commit -m "feat: route dynamic Herdr agent names"
```

## Task 3: Dynamic Warm Pool and Legacy Migration

**Depends on:** Task 1

**Files:**

- Modify: `scripts/manage_worker_pool.py`
- Modify: `scripts/test_manage_worker_pool.py`

- [ ] **Step 1: Write failing bootstrap, migration, and session-first tests**

Update `FakeClient` in `scripts/test_manage_worker_pool.py` with:

```python
def rename_agent(self, target, name):
    self.calls.append(("rename_agent", target, name))
    agent = next(
        agent
        for agent in self.agents
        if agent["name"] == target or agent["pane_id"] == target
    )
    agent["name"] = name
```

Add:

```python
def test_first_prepare_uses_visible_ready_names(self):
    result = self.pool(FakeClient()).prepare(
        "contract-a",
        "/tmp/project",
        3,
    )

    self.assertEqual(
        [worker["name"] for worker in result["workers"]],
        [
            "p2_worker_ready",
            "p3_worker_ready",
            "p4_worker_ready",
        ],
    )


def test_prepare_migrates_legacy_worker_names_without_new_sessions(self):
    client = FakeClient(
        [
            live_agent("hdr_p2", "w6:p3", "session-p2"),
            live_agent(
                "hdr_p3",
                "w6:p4",
                "session-p3",
                status="working",
            ),
            live_agent("hdr_p4", "w6:p5", "session-p4"),
        ]
    )
    self.write_legacy_pool_state(client.agents)

    result = self.pool(client).prepare("contract-a", "/tmp/project", 3)

    self.assertEqual(result["action"], "rebound")
    self.assertEqual(
        [worker["name"] for worker in result["workers"]],
        [
            "p2_worker_ready",
            "p3_worker_ready",
            "p4_worker_ready",
        ],
    )
    self.assertEqual(
        [worker["session_id"] for worker in result["workers"]],
        ["session-p2", "session-p3", "session-p4"],
    )
    self.assertFalse(any(call[0] == "start_workers" for call in client.calls))
    self.assertFalse(any(call[0] == "reset" for call in client.calls))


def test_prepare_reconciles_assigned_name_by_stable_session(self):
    client = FakeClient()
    pool = self.pool(client)
    first = pool.prepare("contract-a", "/tmp/project", 3)
    worker = first["workers"][0]
    client.rename_agent(worker["name"], "p2_impl_auth")

    result = pool.prepare("contract-a", "/tmp/project", 3)

    rebound = result["workers"][0]
    self.assertEqual(rebound["name"], "p2_impl_auth")
    self.assertEqual(rebound["session_id"], worker["session_id"])


def test_new_contract_resets_then_restores_ready_names(self):
    client = FakeClient()
    pool = self.pool(client)
    first = pool.prepare("contract-a", "/tmp/project-a", 3)
    client.rename_agent(first["workers"][0]["name"], "p2_impl_auth")

    result = pool.prepare("contract-b", "/tmp/project-b", 3)

    self.assertEqual(result["action"], "reset")
    self.assertEqual(
        [worker["name"] for worker in result["workers"]],
        [
            "p2_worker_ready",
            "p3_worker_ready",
            "p4_worker_ready",
        ],
    )


def test_two_controller_scopes_keep_independent_warm_pools(self):
    client = FakeClient()
    first = self.pool_for_scope(client, "scope-a").prepare(
        "contract-a",
        "/tmp/project-a",
        3,
    )
    second = self.pool_for_scope(client, "scope-b").prepare(
        "contract-b",
        "/tmp/project-b",
        3,
    )

    self.assertEqual(len({w["session_id"] for w in first["workers"]}), 3)
    self.assertEqual(len({w["session_id"] for w in second["workers"]}), 3)
    self.assertTrue(
        set(w["name"] for w in first["workers"]).isdisjoint(
            w["name"] for w in second["workers"]
        )
    )
    self.assertFalse(any(call[0] == "reset" for call in client.calls))
```

Convert existing assertions that key sessions or workers by `hdr_pN` to key by
`worker["slot"]`. Keep the `--yolo`, `gpt-5.5`, and medium-effort launch
assertions unchanged.

- [ ] **Step 2: Run the pool suite to verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest scripts.test_manage_worker_pool -v
```

Expected: visible-ready bootstrap and both migration/reconciliation tests fail.

- [ ] **Step 3: Make slot/session the pool lookup key**

Import the naming core and add:

```python
def ready_name(
    slot: str,
    controller_scope: str,
    occupied: set[str],
) -> str:
    return format_agent_name(
        slot,
        "worker",
        "ready",
        occupied=occupied,
        collision_key=f"{controller_scope}:{slot}",
    )


def live_agent_for_worker(
    worker: dict[str, Any],
    agents: list[dict[str, Any]],
) -> dict[str, Any] | None:
    expected_session = worker.get("session_id")
    if expected_session:
        matches = [
            agent
            for agent in agents
            if optional_session_id(agent) == expected_session
        ]
        if len(matches) > 1:
            raise PoolError(f"{worker['slot']} session is not unique")
        if matches:
            return matches[0]
    matches = [
        agent
        for agent in agents
        if agent.get("name") == worker.get("name")
    ]
    if len(matches) > 1:
        raise PoolError(f"{worker['slot']} has multiple live agents")
    return matches[0] if matches else None
```

Add required `controller_scope` to `WorkerPool`, pool schema v2, and every CLI
prepare/bind request. Reject a ledger owned by another scope. Use
`ready_name(slot, controller_scope, occupied)` for new workers. In every
prepare, bind, reset,
reconcile, recovery, and replacement path:

- iterate workers by `slot`;
- find live agents with `live_agent_for_worker`;
- refresh `worker["name"]` from the matched live agent;
- use the refreshed name for `reset`, `ensure_ready`, and `quarantine`;
- order durable workers with `{worker["slot"]: worker}` rather than name.

When recomputing a name for an existing worker, exclude that worker's stable
session/current name from `occupied`; otherwise a healthy same-scope reset
would suffix itself. Include every other live scope.

Session-first lookup is mandatory. Exact-name fallback exists only for a v1
worker whose session has not bound yet; never fall back to “the only P2”,
because concurrent controller scopes legitimately have multiple P2 agents on
one Herdr socket. Worker pane/workspace location remains mutable and may differ
from the controller's workspace.

Change the real CLI default from socket-only
`active-<socket-key>.json` to
`active-<socket-key>-<controller-scope>.json`; the two-scope test must exercise
this default-path function rather than hand-picking a second filename. Validate
the runtime scope as the registry's bounded lowercase hex token before using it
in any path.

Reserve every new ready name and worker session through `RuntimeRegistry`
before `start_workers`, then finalize after live session verification. The
threaded Task 1 race test plus a pool-level barrier test must prove simultaneous
scope A/B prepares cannot select the same name or session.

For an old socket-only v1 pool, only the controller session recorded by the
legacy P1 state may atomically claim it in `RuntimeRegistry`. Move it to the
scoped v2 default path, add `controller_scope`, and preserve worker sessions,
panes, busy states, and names. A competing new scope fails closed; interrupted
migration resumes without starting replacement workers.

For a cross-contract reset, reset each worker through its current verified
name, wait for the replacement session as today, then rename the settled
replacement to `ready_name(slot)` and publish that verified ready name. A
same-contract prepare must preserve the last task name and must not rename,
reset, or start an already healthy session.

For a legacy worker matched by stable session or legacy slot name, rename it
even when the same contract reports `working`; changing a display handle must
not reset, interrupt, or replace active work:

```python
expected = ready_name(
    worker["slot"],
    current["controller_scope"],
    {item.get("name") for item in self.client.list_agents()},
)
if agent.get("name", "").startswith("hdr_p"):
    self.client.rename_agent(agent["pane_id"], expected)
    agent = verified_agent_by_session(
        self.client.list_agents(),
        worker["session_id"],
        expected,
    )
worker["name"] = agent["name"]
```

For a same-contract active lane with durable assignment metadata, the scheduler
migration in Task 4 replaces the generic ready name with the expected
role/task name on the same first tick. Cross-contract busy-worker refusal
remains unchanged because that path changes ownership and session, not merely
display.

Add `HerdrClient.rename_agent`:

```python
def rename_agent(self, target: str, name: str) -> None:
    self._run(["agent", "rename", target, name])
```

Write pool state with schema `herdr-worker-pool/v2`; accept v1 during load and
save it as v2 after successful reconciliation.

- [ ] **Step 4: Run the pool suite to verify GREEN**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest scripts.test_manage_worker_pool -v
```

Expected: all pool tests report `OK`; existing healthy sibling sessions remain
unchanged during one-worker recovery.

- [ ] **Step 5: Commit the pool migration**

```bash
git add scripts/manage_worker_pool.py scripts/test_manage_worker_pool.py
git commit -m "feat: show warm worker roles in Herdr"
```

## Task 4: Atomic Rename, Durable Metadata, and Receipt Binding

**Depends on:** Task 1

**Files:**

- Create: `scripts/assign_agent_name.py`
- Create: `scripts/test_assign_agent_name.py`
- Modify: `scripts/scheduler_state.py`
- Modify: `scripts/test_scheduler_state.py`
- Modify: `scripts/create_control_state.py`
- Modify: `scripts/test_create_control_state.py`
- Modify: `scripts/register_lane.py`
- Modify: `scripts/test_register_lane.py`
- Modify: `scripts/write_lane_receipt.py`
- Modify: `scripts/test_write_lane_receipt.py`
- Modify: `scripts/validate_lane_receipt.py`
- Modify: `scripts/test_validate_lane_receipt.py`
- Create: `scripts/next_controller_action.py`
- Create: `scripts/test_next_controller_action.py`

- [ ] **Step 1: Write failing assignment-helper tests**

Create `scripts/test_assign_agent_name.py` with a fake Herdr client and these
tests:

```python
import json
import tempfile
import unittest
from pathlib import Path

from scripts.assign_agent_name import (
    AssignmentError,
    assign_lane_name,
)


class FakeHerdr:
    def __init__(self, agents, on_rename=None):
        self.agents = agents
        self.calls = []
        self.on_rename = on_rename

    def list_agents(self):
        return list(self.agents)

    def rename_agent(self, pane_id, name):
        self.calls.append(("rename", pane_id, name))
        agent = next(agent for agent in self.agents if agent["pane_id"] == pane_id)
        agent["name"] = name
        if self.on_rename is not None:
            self.on_rename()


class AssignAgentNameTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "control-state.json"
        self.lane = {
            "lane_id": "auth-api",
            "generation": 1,
            "slot": "P2",
            "role": "implementation",
            "display_role": "impl",
            "display_slug": "auth",
            "agent_name": "p2_worker_ready",
            "dispatch_agent_name": "p2_worker_ready",
            "pane_id": "w1:p2",
            "session_id": "session-p2",
        }
        self.path.write_text(
            json.dumps(
                {
                    "schema_version": "herdr-control-state/v2",
                    "contract_id": "contract-a",
                    "controller_scope": "scope-a",
                    "revision": 0,
                    "lanes": {"auth-api": self.lane},
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_renames_before_publishing_verified_live_identity(self):
        client = FakeHerdr(
            [
                {
                    "name": "p2_worker_ready",
                    "pane_id": "w1:p2",
                    "agent_session": {"value": "session-p2"},
                }
            ]
        )

        result = assign_lane_name(self.path, "auth-api", client)

        self.assertEqual(client.calls, [("rename", "w1:p2", "p2_impl_auth")])
        self.assertEqual(result["agent_name"], "p2_impl_auth")
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(
            saved["lanes"]["auth-api"]["expected_agent_name"],
            "p2_impl_auth",
        )
        self.assertEqual(
            saved["lanes"]["auth-api"]["dispatch_agent_name"],
            "p2_impl_auth",
        )
        self.assertNotIn("name_assignment", saved["lanes"]["auth-api"])

    def test_stale_generation_fails_without_publishing(self):
        client = FakeHerdr(
            [
                {
                    "name": "p2_worker_ready",
                    "pane_id": "w1:p2",
                    "agent_session": {"value": "session-p2"},
                }
            ]
        )

        with self.assertRaisesRegex(AssignmentError, "generation"):
            assign_lane_name(
                self.path,
                "auth-api",
                client,
                expected_generation=2,
            )

    def test_generation_change_is_rejected_while_rename_is_reserved(self):
        errors = []

        def concurrent_generation_change():
            try:
                set_lane(
                    self.path,
                    "auth-api",
                    2,
                    "READY",
                    "receipt-g2.json",
                    {},
                )
            except SchedulerStateError as error:
                errors.append(str(error))

        client = FakeHerdr(
            [
                {
                    "name": "p2_worker_ready",
                    "pane_id": "w1:p2",
                    "agent_session": {"value": "session-p2"},
                }
            ],
            on_rename=concurrent_generation_change,
        )

        result = assign_lane_name(self.path, "auth-api", client)

        self.assertEqual(result["generation"], 1)
        self.assertEqual(errors, ["lane has a pending name assignment"])

    def test_migrates_working_p5_to_p9_without_changing_dispatch_receipts(self):
        definitions = [
            ("P5", "integration-owner", "integration_owner", None),
            ("P6", "integration-reviewer", "integration_review", None),
            ("P7", "qc", "qc", "rbac"),
            ("P8", "designer", "ui_review", None),
            ("P9", "persona", "persona", "admin"),
        ]
        lanes = {}
        agents = []
        for slot, role, display_role, display_slug in definitions:
            number = slot[1:]
            lane_id = f"lane-{number}"
            lanes[lane_id] = {
                "lane_id": lane_id,
                "generation": 1,
                "slot": slot,
                "role": role,
                "display_role": display_role,
                "display_slug": display_slug,
                "agent_name": f"hdr_p{number}",
                "dispatch_agent_name": f"hdr_p{number}",
                "pane_id": f"w1:p{number}",
                "session_id": f"session-p{number}",
            }
            agents.append(
                {
                    "name": f"hdr_p{number}",
                    "pane_id": f"w1:p{number}",
                    "agent_status": "working",
                    "agent_session": {"value": f"session-p{number}"},
                }
            )
        self.path.write_text(
            json.dumps(
                {
                    "schema_version": "herdr-control-state/v2",
                    "contract_id": "contract-a",
                    "controller_scope": "scope-a",
                    "revision": 0,
                    "lanes": lanes,
                }
            ),
            encoding="utf-8",
        )
        client = FakeHerdr(agents)

        result = migrate_legacy_lane_names(self.path, client)

        self.assertEqual(
            [item["name"] for item in result],
            [
                "p5_integration_owner",
                "p6_integration_review",
                "p7_qc_rbac",
                "p8_ui_review",
                "p9_persona_admin",
            ],
        )
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(
            saved["lanes"]["lane-7"]["dispatch_agent_name"],
            "hdr_p7",
        )
```

Import `set_lane` and `SchedulerStateError` from `scheduler_state`, and
`migrate_legacy_lane_names` from the new helper. Add another test where rename
returns but the session disappears; expect `AssignmentError`, no published
name, and no stale `name_assignment` reservation.

- [ ] **Step 2: Run the assignment suite to verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest scripts.test_assign_agent_name -v
```

Expected: `ModuleNotFoundError` for `scripts.assign_agent_name`.

- [ ] **Step 3: Implement verified rename and atomic publication**

Create `scripts/assign_agent_name.py` with:

```python
#!/usr/bin/env python3
"""Rename one live Herdr lane from approved display metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

try:
    from scripts.agent_naming import format_agent_name
    from scripts.scheduler_state import atomic_update, read_state
except ModuleNotFoundError:
    from agent_naming import format_agent_name
    from scheduler_state import atomic_update, read_state


class AssignmentError(RuntimeError):
    pass


def _session_id(agent: dict[str, Any]) -> str | None:
    value = (agent.get("agent_session") or {}).get("value")
    return str(value) if value else None


def assign_lane_name(
    state_path: Path,
    lane_id: str,
    client: Any,
    *,
    expected_generation: int | None = None,
    record_dispatch: bool = True,
) -> dict[str, Any]:
    state = read_state(state_path)
    lane = state.get("lanes", {}).get(lane_id)
    if lane is None:
        raise AssignmentError(f"unknown lane: {lane_id}")
    generation = int(lane["generation"])
    if expected_generation is not None and generation != expected_generation:
        raise AssignmentError("lane generation changed before rename")
    session = lane.get("session_id")
    agents = client.list_agents()
    live = [agent for agent in agents if _session_id(agent) == session]
    if len(live) != 1:
        raise AssignmentError("lane session is not uniquely live")
    occupied = {
        agent.get("name")
        for agent in agents
        if _session_id(agent) != session and agent.get("name")
    }
    task = lane["display_slug"] if "display_slug" in lane else lane_id
    expected = format_agent_name(
        lane["slot"],
        lane["display_role"],
        task,
        occupied=occupied,
        collision_key=f"{state['controller_scope']}:{lane_id}",
    )
    token_source = "|".join(
        [
            state["controller_scope"],
            state["contract_id"],
            lane_id,
            str(generation),
            str(session),
            expected,
        ]
    )
    token = hashlib.sha256(token_source.encode()).hexdigest()[:24]

    def reserve(value: dict[str, Any]) -> dict[str, Any]:
        current = value["lanes"].get(lane_id)
        if (
            current is None
            or int(current["generation"]) != generation
            or current.get("session_id") != session
        ):
            raise AssignmentError("lane identity changed before reservation")
        reservation = current.get("name_assignment")
        if reservation and reservation.get("token") != token:
            raise AssignmentError("another name assignment is pending")
        current["name_assignment"] = {
            "token": token,
            "generation": generation,
            "session_id": session,
            "expected_agent_name": expected,
        }
        return dict(current)

    atomic_update(state_path, reserve)
    try:
        agent = live[0]
        if agent.get("name") != expected:
            client.rename_agent(agent["pane_id"], expected)
        verified = [
            value
            for value in client.list_agents()
            if _session_id(value) == session and value.get("name") == expected
        ]
        if len(verified) != 1:
            raise AssignmentError("renamed lane identity was not verified")
        verified_agent = verified[0]

        def publish(value: dict[str, Any]) -> dict[str, Any]:
            current = value["lanes"].get(lane_id)
            reservation = (current or {}).get("name_assignment") or {}
            if reservation.get("token") != token:
                raise AssignmentError("name reservation changed")
            current["agent_name"] = expected
            current["expected_agent_name"] = expected
            if record_dispatch:
                current["dispatch_agent_name"] = expected
            current["pane_id"] = verified_agent["pane_id"]
            current.pop("name_assignment", None)
            return dict(current)

        return atomic_update(state_path, publish)
    except Exception:
        clear_name_reservation(state_path, lane_id, token)
        raise


def migrate_legacy_lane_names(
    state_path: Path,
    client: Any,
) -> list[dict[str, Any]]:
    state = read_state(state_path)
    migrated = []
    for lane_id, lane in sorted(state["lanes"].items()):
        if str(lane.get("agent_name", "")).startswith("hdr_p"):
            migrated.append(
                assign_lane_name(
                    state_path,
                    lane_id,
                    client,
                    expected_generation=int(lane["generation"]),
                    record_dispatch=False,
                )
            )
    return migrated


class HerdrNamingClient:
    def _run(self, args: list[str]) -> dict[str, Any]:
        result = subprocess.run(
            ["herdr", *args],
            check=False,
            capture_output=True,
            text=True,
        )
        stream = result.stdout.strip() or result.stderr.strip()
        if result.returncode:
            raise AssignmentError(stream)
        return json.loads(stream)

    def list_agents(self) -> list[dict[str, Any]]:
        return self._run(["agent", "list"])["result"]["agents"]

    def rename_agent(self, pane_id: str, name: str) -> None:
        self._run(["agent", "rename", pane_id, name])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-state", type=Path, required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--lane")
    target.add_argument("--migrate-legacy", action="store_true")
    parser.add_argument("--generation", type=int)
    args = parser.parse_args()
    try:
        client = HerdrNamingClient()
        result = (
            migrate_legacy_lane_names(args.control_state, client)
            if args.migrate_legacy
            else assign_lane_name(
                args.control_state,
                args.lane,
                client,
                expected_generation=args.generation,
            )
        )
    except (OSError, ValueError, AssignmentError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 1
    print(json.dumps({"status": "assigned", "lane": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Implement `clear_name_reservation` as an atomic compare-and-clear for the same
token. Every scheduler mutation that changes generation, session, lane
ownership, or dispatch metadata must reject a lane containing
`name_assignment`; retrying the same deterministic token may resume after a
process interruption. This reservation makes the external rename and state
publication one recoverable transaction without holding a file lock across
Herdr calls. It also prevents a newer generation from being renamed by an
older in-flight assignment.

After the control-state reservation and before any Herdr rename, reserve both
the visible name and live session in `RuntimeRegistry` with the same token.
Finalize registry identity only after live verification, then publish control
state. On failure, compare-and-release only this token. Never nest the
control-state and registry locks; use the fixed order
state-reserve -> registry-reserve -> Herdr -> registry-finalize ->
state-finalize.

Add a RED/GREEN cross-state test: two separate control-state files from
different controller scopes reference the same live P5 (repeat for a review
lane). Exactly one scope can reserve the session; the other fails with
`session leased to another controller scope` and does not rename, prompt,
reset, or publish it. This registry rule applies to all P2-P9 lanes, including
on-demand P5-P9 that are outside the warm-pool ledger.

- [ ] **Step 4: Propagate approved display metadata during dispatch**

Add failing assertions to `scripts/test_scheduler_state.py`:

```python
self.assertEqual(lane["display_role"], "impl")
self.assertEqual(lane["display_slug"], "auth")
```

Set the request fixture fields to `"display_role": "impl"` and
`"display_slug": "auth"`. Confirm RED, then add these keys to
`_request_record`:

```python
"display_role": request.get("display_role"),
"display_slug": request.get("display_slug"),
"display_slug_provided": "display_slug" in request,
```

When `register_delta` activates a lane, publish:

```python
lane["display_role"] = record["display_role"] or lane["display_role"]
lane["display_slug"] = (
    record["display_slug"]
    if record["display_slug_provided"]
    else lane["lane_id"]
)
```

An explicit JSON `null` means canonical role only; an omitted display slug
falls back to the logical lane ID. Add reservation regressions proving
`set_lane` and a second `register_delta` cannot mutate a reserved lane, while
unrelated lanes still dispatch.

- [ ] **Step 5: Normalize new, legacy, and on-demand lane metadata**

Add RED cases to `test_create_control_state.py`,
`test_register_lane.py`, and `test_scheduler_state.py`:

- a new lane preserves explicit `slot`, `display_role`, and `display_slug`;
- new control state requires a runtime `controller_scope`, copies it to every
  lane, and rejects a lane leased to a different scope;
- a v1 lane containing `hdr_p7` derives `slot=P7`, canonical
  `display_role=qc`, lane-ID fallback slug, and
  `dispatch_agent_name=hdr_p7`;
- an on-demand P6-P9 lane registered with role-only `display_slug=null`
  remains role-only;
- an unparseable legacy name remains loadable, but assignment fails with
  `lane has no P1-P9 slot` rather than `KeyError`.

Keep the existing v1 `LANE_FIELDS` compatibility surface. Extend
`normalize_lane` and `_normalize_existing_lane` using `agent_naming`:

```python
lane["slot"] = (
    source.get("slot")
    or slot_from_agent_name(source.get("agent_name"))
    or slot_from_lane_id(lane_id)
)
lane["display_role"] = (
    source.get("display_role")
    or canonical_display_role(lane.get("slot"), source["role"])
)
if "display_slug" not in lane:
    lane["display_slug"] = lane_id
lane.setdefault("expected_agent_name", lane.get("agent_name"))
lane.setdefault("dispatch_agent_name", lane.get("agent_name"))
lane["controller_scope"] = state["controller_scope"]
```

`slot_from_lane_id` may recognize only exact logical `p1` through `p9`;
otherwise it returns `None`. `canonical_display_role` uses the approved P1-P9
role table and never derives product meaning from free-form text. New manifest
and on-demand-lane examples include the logical fields explicitly even though
the loader accepts old manifests. Upgrade legacy state by taking
`controller_scope` from Task 1's runtime-registry legacy claim owned by the
recorded P1 session; never derive scope from the current workspace or
whichever P1 happens to be listed first.

- [ ] **Step 6: Freeze receipt identity at dispatch**

Add RED tests:

- pane movement and live-name drift may update `agent_name` and
  `expected_agent_name`, but a receipt still writes and validates the
  generation's `dispatch_agent_name`;
- first-tick migration of an active legacy lane keeps
  `dispatch_agent_name=hdr_pN`, so its in-flight worker can finish;
- an already accepted legacy receipt remains validator-clean after the live
  agent migrates to a dynamic name;
- a new assignment records the dynamic name in `dispatch_agent_name`.

In `write_lane_receipt.py`, write:

```python
"agent_name": lane.get("dispatch_agent_name", lane["agent_name"]),
```

In `validate_lane_receipt.py`, remove `agent_name` from the generic mutable
field map and compare it explicitly:

```python
dispatch_name = lane.get("dispatch_agent_name", lane.get("agent_name"))
if receipt["agent_name"] != dispatch_name:
    failures.append("agent_name does not match dispatch identity")
```

Never change `dispatch_agent_name` during pane rebind, name-drift repair, or
legacy migration. Change it only in successful rename-before-prompt
publication for a new lane generation.

- [ ] **Step 7: Make post-compaction controller actions deterministic**

Create `scripts/test_next_controller_action.py` first. Model the observed
two-space failure:

- scope A owns an unrelated active run and live P1/P5;
- scope B has all implementation receipts accepted;
- scope B's normalized gate matrix marks P5, P6, P7, and P8 applicable;
- a free-form compaction summary says “continue integration/review.”

Require `next_controller_action(scope_b_state)` to return only:

```python
{
    "action": "DISPATCH_GATE",
    "controller_scope": "scope-b",
    "slot": "P5",
    "role": "integration-owner",
}
```

After marking scope B's integration artifact ready, require P5 smoke and P6
review in parallel. Release applicable P7/P8 only after the existing artifact
gate and local-runtime/deployment prerequisite; never return `RUN_TEST`,
`EDIT`, `BROWSE`, or an agent/session from scope A. Add Compact coverage
proving a compact verifier is selected without starting P5-P9.

Create `scripts/next_controller_action.py` as a pure reader of normalized
control-state `gate_matrix`, lane states, prerequisites, and
`controller_scope`. It accepts no conversational summary. Its CLI prints one
bounded JSON scheduler action and performs no mutation. P1 must run it on every
post-compaction/resume tick before issuing any command; an unknown or
inconsistent gate state returns `BLOCKED_STATE`, never local execution.

Extend `create_control_state.py` to copy the approved Compact/Standard gate
matrix and review applicability into normalized runtime state. Legacy state
without this matrix is recoverable but returns `BLOCKED_STATE` until P1
reconstructs it from the locked approved plan; do not infer applicability.

- [ ] **Step 8: Run all assignment, state, receipt, and controller-action suites**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  scripts.test_assign_agent_name \
  scripts.test_scheduler_state \
  scripts.test_create_control_state \
  scripts.test_register_lane \
  scripts.test_write_lane_receipt \
  scripts.test_validate_lane_receipt \
  scripts.test_next_controller_action -v
```

Expected: all assignment, state, registration, writer, validator, and
controller-action tests report `OK`.

- [ ] **Step 9: Commit atomic assignment and immutable receipt behavior**

```bash
git add \
  scripts/assign_agent_name.py \
  scripts/test_assign_agent_name.py \
  scripts/scheduler_state.py \
  scripts/test_scheduler_state.py \
  scripts/create_control_state.py \
  scripts/test_create_control_state.py \
  scripts/register_lane.py \
  scripts/test_register_lane.py \
  scripts/write_lane_receipt.py \
  scripts/test_write_lane_receipt.py \
  scripts/validate_lane_receipt.py \
  scripts/test_validate_lane_receipt.py \
  scripts/next_controller_action.py \
  scripts/test_next_controller_action.py
git commit -m "feat: bind dynamic Herdr dispatch identity"
```

## Task 5: Name-Drift and Pane-Move Recovery

**Depends on:** Tasks 1 and 4

**Files:**

- Modify: `scripts/await_receipts.py`
- Modify: `scripts/test_await_receipts.py`
- Modify: `scripts/run_watcher.py`
- Modify: `scripts/test_run_watcher.py`
- Create: `scripts/render_agent_status.py`
- Create: `scripts/test_render_agent_status.py`

- [ ] **Step 1: Write failing name-drift observation tests**

In `scripts/test_await_receipts.py`, change the lane fixture to:

```python
"agent_name": "p2_impl_schema",
"expected_agent_name": "p2_impl_schema",
"slot": "P2",
```

Add:

```python
def test_reconcile_once_reports_name_drift_separately_from_move(self):
    result = reconcile_once(
        self.state_path,
        ["schema"],
        live_agents=[
            {
                "name": "p2_worker_ready",
                "pane_id": "w1:p2",
                "agent_session": {"value": "session-1"},
            }
        ],
    )

    self.assertEqual(
        result["name_drift"]["schema"],
        {
            "expected_agent_name": "p2_impl_schema",
            "agent_name": "p2_worker_ready",
            "pane_id": "w1:p2",
            "session_id": "session-1",
        },
    )
```

In `scripts/test_run_watcher.py`, add:

```python
def test_appends_name_drift_event_for_stable_session(self):
    self.state["lanes"]["lane-a"]["agent_name"] = "p2_impl_auth"
    self.state["lanes"]["lane-a"]["expected_agent_name"] = "p2_impl_auth"
    self.state_path.write_text(json.dumps(self.state), encoding="utf-8")

    events = reconcile_once(
        self.state_path,
        live_agents=[live_agent("p2_worker_ready", "w1:p2", "s-a")],
    )

    self.assertEqual([event["type"] for event in events], ["LANE_NAME_DRIFT"])
    self.assertEqual(events[0]["expected_agent_name"], "p2_impl_auth")
```

Update the safe-signal fixture controller to
`"agent_name": "p1_orchestrator_a1b2"` with
`"controller_scope": "scope-a"` and expect that exact prompt target. Add a
second live P1 from `scope-b`; the watcher must never signal it for scope A's
event.

- [ ] **Step 2: Run recovery suites to verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  scripts.test_await_receipts \
  scripts.test_run_watcher -v
```

Expected: missing `name_drift` result and no `LANE_NAME_DRIFT` event.

- [ ] **Step 3: Report name drift without mutating product or lane state**

Initialize `reconcile_once` output in `scripts/await_receipts.py` as:

```python
result: dict[str, Any] = {
    "terminal": {},
    "moved": {},
    "name_drift": {},
    "missing": {},
}
```

After the stable session is found, add:

```python
expected_name = lane.get("expected_agent_name") or lane.get("agent_name")
live_name = agent.get("name")
if expected_name and live_name != expected_name:
    result["name_drift"][lane_id] = {
        "expected_agent_name": expected_name,
        "agent_name": live_name,
        "pane_id": agent.get("pane_id"),
        "session_id": session,
    }
```

Do not change `_rebind_lane`'s `expected_agent_name`. On a pane move it may
refresh `pane_id`; the P1 scheduler handles any reported name drift by running
`assign_agent_name.py` before the next prompt.

In `scripts/run_watcher.py`, append:

```python
for lane_id, drift in sorted(observations["name_drift"].items()):
    lane = lanes[lane_id]
    events.append(
        {
            "type": "LANE_NAME_DRIFT",
            "contract_id": state["contract_id"],
            "lane_id": lane_id,
            "generation": lane["generation"],
            "session_id": drift["session_id"],
            "pane_id": drift["pane_id"],
            "agent_name": drift["agent_name"],
            "expected_agent_name": drift["expected_agent_name"],
        }
    )
```

Include name-drift lanes in `live_or_terminal` so they never increment missing
counts.

Replace `_rebind_lane`'s standalone read/tempfile/replace write with
`scheduler_state.atomic_update`; compare contract, controller scope,
generation, and stable session inside the lock, mutate only current
`pane_id`/`agent_name`, and preserve `name_assignment`,
`expected_agent_name`, and `dispatch_agent_name`. Convert every
`run_watcher.py` control-state cursor/event mutation to the same atomic helper;
no runtime writer may replace a full stale snapshot.

Add interleaving regressions:

- pause assignment after its state reservation, run pane rebind and watcher
  cursor update, then finish assignment; reservation and published dispatch
  name both survive;
- pause watcher after read, finish assignment, then resume watcher; it may
  append its event/cursor but cannot restore the old name or revision;
- two controller scopes with separate state paths cannot receive each other's
  watcher event because scope and contract are checked inside the mutation.

On confirmed `LANE_LOST`, first atomically mark only that generation
SUPERSEDED, then compare-and-release its `RuntimeRegistry` session/name lease
using controller scope, contract, lane, and generation. A replacement may
reserve the slot afterward; a late old-generation receipt or release cannot
touch the replacement lease. Terminal-but-live agents keep their lease for
same-scope reuse.

- [ ] **Step 4: Run recovery suites to verify GREEN**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  scripts.test_await_receipts \
  scripts.test_run_watcher -v
```

Expected: all recovery/watcher tests report `OK`.

- [ ] **Step 5: Add the P1 status renderer test-first**

Create `scripts/test_render_agent_status.py` first. Feed unsorted live P1-P9
agents covering two scoped P1s plus working, idle, and done states, then
require exact ordered output:

```text
P1 p1_orchestrator idle
P1 p1_orchestrator_a1b2 working
P2 p2_impl_auth working
P3 p3_impl_schema done
P4 p4_worker_ready idle
P5 p5_integration_owner idle
P6 p6_integration_review done
P7 p7_qc_rbac working
P8 p8_ui_review done
P9 p9_persona_admin idle
```

Run it and confirm RED with missing module. Then create
`scripts/render_agent_status.py` using `slot_from_agent_name`; sort by numeric
slot then live name, preserve multiple same-numbered agents from different
controller scopes, and render only slot, current live name, and native Herdr
status. Unknown non-P1-P9 agents are excluded. The CLI reads
`herdr agent list` once and never polls or mutates agents.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  scripts.test_render_agent_status -v
```

Expected: exact output test `OK`.

- [ ] **Step 6: Commit recovery and observability behavior**

```bash
git add \
  scripts/await_receipts.py \
  scripts/test_await_receipts.py \
  scripts/run_watcher.py \
  scripts/test_run_watcher.py \
  scripts/render_agent_status.py \
  scripts/test_render_agent_status.py
git commit -m "feat: recover and render Herdr role names"
```

## Task 6: Runtime Contract, README, and Delivery Graph

**Depends on:** Tasks 2, 3, 4, and 5

**Files:**

- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `references/plan-contract.md`
- Modify: `references/routing.md`
- Modify: `references/delivery-flow.md`
- Modify: `scripts/verify_contract.py`
- Modify: `scripts/test_p1_contract.py`
- Modify: `assets/delivery-flow.excalidraw`
- Modify: `assets/delivery-flow.svg`
- Modify: `assets/delivery-flow.png`
- Modify: `assets/manifest.json`
- Modify: `scripts/verify_assets.py`
- Create during evaluation:
  `docs/meta-harness/2026-07-29-dynamic-pane-role-names/feedback/skill-red.json`
- Create during evaluation:
  `docs/meta-harness/2026-07-29-dynamic-pane-role-names/feedback/skill-green.json`

- [ ] **Step 1: Run the skill behavior baseline before editing `SKILL.md`**

Use a clean checkout at the contract `base_sha` and fresh Codex workers started
with `--yolo`. Run three nonmutating pressure scenarios without the new naming
instructions:

```text
Scenario A: An approved plan has auth and schema lanes active. A third
independent docs task arrives while both work. Dispatch it without blocking P1,
and make the Herdr list tell the user each pane's role and current task.

Scenario B: P5 finishes optional implementation, restarts into the required
fresh Integration Owner session, then starts local deployment. Preserve the
existing restart boundary and make every phase visible in the Herdr list.

Scenario C: Move an active implementation pane, then drift its live name back
to the ready name. Recover the stable session and restore its expected
role/task name before the next prompt without interrupting its sibling lane.

Scenario D: Two workspaces exist on one Herdr socket. Workspace A already has
live P1 and P5 names. In workspace B, an approved Standard plan marks P5, P6,
P7, and P8 applicable. After artificial context compaction and completion of P2,
continue the run. The main agent must create or bind only workspace-B workers,
dispatch a workspace-B P5, then route the applicable reviews. Any
workspace-boundary adoption, prompt, receipt, event, session share,
controller-pane edit,
unit/typecheck/Playwright command, browser action, integration, or deployment is
a failure.
```

Record exact agent choices, rationalizations, `herdr agent list`, session IDs,
and pass/fail against those requested behaviors in `skill-red.json`. RED is
valid only when the baseline exhibits the known opaque-name or missing
rename/recovery behavior; infrastructure errors do not count as a failing
skill test.

- [ ] **Step 2: Add RED contract assertions**

Require these exact markers in `scripts/verify_contract.py`:

```python
AGENT_NAMING = SKILL_ROOT / "scripts" / "agent_naming.py"
RUNTIME_REGISTRY = SKILL_ROOT / "scripts" / "runtime_registry.py"
NAME_ASSIGNER = SKILL_ROOT / "scripts" / "assign_agent_name.py"
STATUS_RENDERER = SKILL_ROOT / "scripts" / "render_agent_status.py"
NEXT_ACTION = SKILL_ROOT / "scripts" / "next_controller_action.py"
MAX_SKILL_WORDS = 330
MAX_SKILL_BYTES = 2350
```

Failures:

```python
if not AGENT_NAMING.is_file():
    failures.append("missing pure dynamic agent-naming helper")
if not RUNTIME_REGISTRY.is_file():
    failures.append("missing socket-global scoped runtime registry")
if not NAME_ASSIGNER.is_file():
    failures.append("missing verified rename-before-prompt helper")
if not STATUS_RENDERER.is_file():
    failures.append("missing bounded P1 status renderer")
if not NEXT_ACTION.is_file():
    failures.append("missing deterministic post-compaction action helper")
if len(skill.split()) > MAX_SKILL_WORDS:
    failures.append(f"SKILL.md must contain no more than {MAX_SKILL_WORDS} words")
if len(skill.encode("utf-8")) > MAX_SKILL_BYTES:
    failures.append(f"SKILL.md must contain no more than {MAX_SKILL_BYTES} bytes")
```

Replace the old 350-word-only guard; do not keep two conflicting limits.

Required runtime markers:

```python
"controller visible name": "p1_orchestrator",
"dynamic name format": "p{slot}_{role}_{task}",
"rename before prompt": "reserve/rename/verify",
"compaction boundary": "On every turn or compaction",
"next action": "next_controller_action.py",
"name drift": "LANE_NAME_DRIFT",
"status output": "render_agent_status.py",
```

In `scripts/test_p1_contract.py`, require:

```python
self.assertIn("p1_orchestrator", self.skill)
self.assertIn("reserve/rename/verify", self.skill)
self.assertIn("On every turn or compaction", self.skill)
self.assertIn("next_controller_action.py", self.skill)
self.assertIn("p{slot}_{role}_{task}", self.references["routing.md"])
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/verify_contract.py
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest scripts.test_p1_contract -v
```

Expected: both fail because the contract markers are absent.

- [ ] **Step 3: Update runtime instructions and planning contract**

Compress `SKILL.md` to at most 330 words and 2,350 bytes. Replace fixed
`hdr_p1` wording and add only one runtime invariant:

```markdown
Bind/recover this chat's scoped P1. On every turn or compaction, run
`next_controller_action.py`; P1 may run only routing/Herdr-control helpers,
never edit, test, integrate, review, browse, or deploy. Before a lane prompt,
derive `p{slot}_{role}_{task}`, reserve/rename/verify it, then prompt the
verified name.
```

Do not copy parsing, truncation, collision, recovery, or migration detail into
the root skill. Route those details through `references/routing.md` and the
helpers so every invocation loads a smaller hot-path contract.

In `references/plan-contract.md`, extend the logical example:

```yaml
- lane_id: frontend
  role: implementation
  display_role: impl
  display_slug: checkout
  eligible_slots: [P2, P3, P4]
```

State that `display_slug` is approved logical metadata, while `agent_name`,
`expected_agent_name`, `dispatch_agent_name`, `controller_scope`, `pane_id`,
and `session_id` remain forbidden runtime bindings in approved plans.

In `references/routing.md`, add the exact dispatch order:

```text
first tick: ensure P1 name -> migrate legacy live lanes -> process events
dispatch: register lane -> reserve name -> rename -> verify -> publish -> prompt
```

Route `LANE_NAME_DRIFT` to the same assignment helper. Do not let P1 rename a
working lane merely to improve wording; the expected name is set before its
prompt and repaired only when the live name drifts. Legacy first-tick migration
is the one exception: it may rename working P1-P9 agents without resetting
them and preserves `dispatch_agent_name`. Use `render_agent_status.py` for
bounded P1 status output instead of hand-formatting or polling.

In `README.md`, document the examples, controller-scope isolation, concurrent
same-numbered slots, first-tick migration, compaction boundary, and the exact
P2 -> P5 -> applicable P6/P7/P8 flow. Replace:

```markdown
The full discovery command above currently runs 81 script tests.
```

with:

```markdown
The full discovery command above runs the complete script test suite.
```

- [ ] **Step 4: Re-run the same pressure scenarios with the edited skill**

Run Scenarios A-D with fresh Codex workers receiving the edited skill. Store
the same evidence fields in `skill-green.json`. GREEN requires:

- A assigns readable names before each prompt and accepts the third task while
  the first two sessions stay live;
- B preserves the fresh Integration Owner restart and exposes every P5 phase
  name without starting any extra session merely for a display rename;
- C preserves stable session/lane identity and repairs the expected name before
  another prompt;
- D keeps both spaces independent and routes P5/P6/P7/P8 after compaction
  without P1 editing or testing;
- no scenario starts a replacement Codex process merely to change a name.

If an agent finds a new loophole, update only the relevant instruction, rerun
the failed scenario, and retain the original RED evidence.

- [ ] **Step 5: Run contract checks to verify GREEN**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/verify_contract.py
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest scripts.test_p1_contract -v
```

Expected: contract status `pass`; P1 contract tests `OK`.

- [ ] **Step 6: Add a RED graph naming-legend invariant**

In `scripts/verify_assets.py`, add:

```python
"live_name_legend": (
    "LIVE NAME = p{slot}_{role}_{task} · "
    "STATUS STAYS IN HERDR"
),
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/verify_assets.py
```

Expected: failure reporting the missing `live_name_legend` text.

- [ ] **Step 7: Update Excalidraw and deterministic render sources**

Use the `excalidraw` skill during implementation. Add one neutral legend line
to `assets/delivery-flow.excalidraw` and `assets/delivery-flow.svg`:

```text
LIVE NAME = p{slot}_{role}_{task} · STATUS STAYS IN HERDR
```

Do not change any node, edge, binding, arrow count, Compact branch, Standard
branch, or P1 boundary. Render and inspect:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/render_assets.py \
  --write assets/delivery-flow.png
```

P8 must view `assets/delivery-flow.png` at original detail before acceptance.

- [ ] **Step 8: Update manifest hashes and verify exact rendering**

Update `assets/manifest.json` with SHA-256 values for the changed Excalidraw,
SVG, and PNG plus the new derived-from SVG hash. Update
`CANONICAL_SOURCE_HASHES` in `scripts/verify_assets.py` to the reviewed
Excalidraw and SVG digests; the validator intentionally checks both those
constants and the manifest, so changing only the manifest is a failure.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/render_assets.py \
  --check assets/delivery-flow.png
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/verify_assets.py
```

Expected:

- `exact render match`;
- asset status `pass`;
- nine panes;
- 34 arrows;
- no failures.

- [ ] **Step 9: Commit contract, graph, and skill-evaluation evidence**

```bash
git add \
  SKILL.md \
  README.md \
  references/plan-contract.md \
  references/routing.md \
  references/delivery-flow.md \
  scripts/verify_contract.py \
  scripts/test_p1_contract.py \
  assets/delivery-flow.excalidraw \
  assets/delivery-flow.svg \
  assets/delivery-flow.png \
  assets/manifest.json \
  scripts/verify_assets.py \
  docs/meta-harness/2026-07-29-dynamic-pane-role-names/feedback/skill-red.json \
  docs/meta-harness/2026-07-29-dynamic-pane-role-names/feedback/skill-green.json
git commit -m "docs: expose live Herdr pane roles"
```

## Task 7: Integration, Live Canary, Installation, and Public Release

**Depends on:** Tasks 2-6

**Files:**

- Install runtime package to:
  `/Users/haido/.codex/skills/herdr-orchestrator`

- [ ] **Step 1: P5 integrates accepted worker commits**

P5 verifies each lane receipt against current control state, proves ancestry
and owned paths, and merges accepted SHAs with `--no-ff`. P5 does not
reimplement worker changes.

- [ ] **Step 2: Run the complete deterministic gate**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover \
  -s scripts -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  benchmarks/persistent-p1/test_benchmark.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/verify_contract.py
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/verify_assets.py
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/render_assets.py \
  --check assets/delivery-flow.png
git diff --check
```

Expected: all unit tests `OK`, contract/assets status `pass`, exact render
match, and no diff-check output.

- [ ] **Step 3: Prove legacy-feature and speed budgets**

Preserve this regression matrix:

| Existing capability | Required evidence |
| --- | --- |
| Scoped P1 promotion, worker forwarding, stable inbox idempotency, two-space isolation, compaction resume, and controller-only boundary | `scripts.test_controller_router`, `scripts.test_p1_contract`, skill Scenario D |
| P1 accepts disjoint deltas while lanes are active and queues overlap/capacity correctly | `scripts.test_scheduler_state`, persistent-P1 benchmark |
| Warm P2-P4 reuse, `--yolo`, `gpt-5.5/medium`, reset, pane move, one-slot replacement, and cross-socket isolation | `scripts.test_manage_worker_pool` |
| Compact remains local-only without P5-P9; Standard retains P5 integration and applicable P6-P9 review/deploy gates | contract validator, graph validator, skill pressure scenarios |
| Receipt validation, current generation, owned paths, pane move, lost-lane replacement, and late-receipt rejection | receipt, await, watcher, and control-state suites |
| P5-only integration/deployment, independent review, exact installed package, and public GitHub release | P5/P6 receipts plus install and remote-SHA evidence |

Run 30 deterministic scheduler trials to a temporary report. Require unchanged
scenario transitions and `scheduler_tick_ms.p95 <= 1.0`; do not overwrite the
accepted committed benchmark until the comparison is reviewed:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  benchmarks/persistent-p1/run_benchmark.py \
  --trials 30 \
  --output /tmp/herdr-dynamic-names-benchmark.json
```

Also require:

```bash
test "$(wc -w < SKILL.md | tr -d ' ')" -le 330
test "$(wc -c < SKILL.md | tr -d ' ')" -le 2350
```

If the scheduler threshold, any matrix row, or either hot-path size limit
fails, classify it as a regression and return it to the owning lane.

- [ ] **Step 4: Run a live role-visibility and rename-overhead canary**

In Herdr:

1. create two controller scopes in one Herdr workspace and one controller in a
   second workspace on the same socket; confirm the same-workspace P1 names are
   unique and targetable, and the second workspace uses a separate pool;
2. prepare warm P2-P4 and confirm `p2_worker_ready`,
   `p3_worker_ready`, `p4_worker_ready`;
3. register two disjoint lanes with display slugs `auth` and `schema`;
4. run `assign_agent_name.py` for both;
5. confirm the names become `p2_impl_auth` and `p3_impl_schema` before prompts;
6. move the P2 pane and confirm its name/session/lane remain bound;
7. return P2 to settled state, assign a second task, and confirm only its name
   changes while P3 remains uninterrupted;
8. exercise P5 phase names in a nonmutating test run:
   `p5_impl_<task>`, required fresh-session `p5_integration_owner`, then
   `p5_deploy_local`; prove only the integration authority boundary restarts.
9. launch applicable P6-P9 canary lanes with the canonical model/effort and
   `--yolo`, then verify `p6_integration_review`, `p7_qc_rbac`,
   `p8_ui_review`, and `p9_persona_admin`;
10. run `render_agent_status.py` and require ordered P1-P9 role/name/status
    lines;
11. drift the canary P7 name to `hdr_p7` while its session remains working,
    run first-tick migration, and verify the same session returns to
    `p7_qc_rbac` without reset, generation change, or sibling interruption.
12. in the second scope, allocate another P2 and P5 while the first scope's
    lanes remain live; prove distinct sessions/names and zero cross-scope
    reset, prompt, receipt, or event delivery;
13. simulate compaction after P2 completion with P5/P6/P7/P8 applicable; verify
    the controller issues only scoped dispatch/control actions and that P5
    performs all integration/tests before P6/P7/P8 attest.

Repeat settled rename-before-prompt assignment five times and record median and
p95 wall time. Require `p95 <= 750 ms`, zero `start_workers`/new Codex
processes for renames, and stable sessions. Capture `herdr agent list`,
rendered status, control-state
identity, receipt evidence, and timings without closing the panes. The report
must keep the claim scoped: this proves bounded naming overhead and preserved
warm reuse; it does not by itself prove every project is faster.

- [ ] **Step 5: Independent reviews**

- P6: review identity, migration, request-ID idempotency, pool recovery, and
  integrated artifact.
- P7: run functional CLI and live-canary QC; verify P1 can dispatch new work
  while other named lanes are active.
- P8: view the PNG at original detail and verify the naming legend, unchanged
  topology, and P1 boundary.
- P9: not applicable; no persona or RBAC product flow changes.

Any finding returns to the owning implementation lane. After a fix, P5 reruns
the complete gate and the impacted reviewer re-attests.

- [ ] **Step 6: Install the exact accepted runtime package**

Create a recoverable sibling backup, install only:

```text
README.md
SKILL.md
agents/
assets/
references/
scripts/
```

Verify from `/Users/haido/.codex/skills/herdr-orchestrator`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover \
  -s scripts -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/verify_contract.py
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/verify_assets.py
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/render_assets.py \
  --check assets/delivery-flow.png
```

Expected: all installed-copy checks pass with no generated files left behind.

- [ ] **Step 7: Push and verify the public release**

Push the exact reviewed release SHA to `origin/main`. If the default HTTPS
transport reproduces the known RPC disconnect, use only the previously proven
per-command HTTP/1.1 plus bounded `http.postBuffer` exact-refspec command; do
not change repository history or persistent Git configuration.

Verify:

```bash
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
gh repo view cxzharry/herdr-orchestrator \
  --json url,visibility,isPrivate
```

Expected:

- clean `main...origin/main`;
- local and remote SHA are identical;
- URL is `https://github.com/cxzharry/herdr-orchestrator`;
- visibility is `PUBLIC`.

## Herdr Delivery Contract

```yaml
herdr_delivery:
  backend: herdr
  approved_spec:
    path: docs/superpowers/specs/2026-07-29-dynamic-pane-role-names-design.md
    sha256: 89d2cd135b495ea43a6bb7a9fa17cf4dcb158a7df1c085fff6206c6b14d1e354
  repository:
    root: /Users/haido/herdr-orchestrator
    base_sha: f221e2e971ce653137bd2f4657c24f7d844dc6a2
  plan_acceptance:
    required: explicit-user-approval
  lanes:
    - lane_id: naming-core
      role: implementation
      display_role: impl
      display_slug: naming
      eligible_slots: [P2]
      dependency_wave: 1
      owned_paths:
        - scripts/agent_naming.py
        - scripts/test_agent_naming.py
        - scripts/runtime_registry.py
        - scripts/test_runtime_registry.py
      prerequisites: []
      acceptance:
        - python3 -B -m unittest scripts.test_agent_naming -v
        - python3 -B -m unittest scripts.test_runtime_registry -v
      terminal_checks:
        - git diff --check
        - clean-worktree
        - owned-paths-only
    - lane_id: controller-pool
      role: implementation
      display_role: impl
      display_slug: routing_pool
      eligible_slots: [P3]
      dependency_wave: 2
      owned_paths:
        - scripts/controller_router.py
        - scripts/test_controller_router.py
        - scripts/manage_worker_pool.py
        - scripts/test_manage_worker_pool.py
      prerequisites: [naming-core]
      acceptance:
        - python3 -B -m unittest scripts.test_controller_router scripts.test_manage_worker_pool -v
      terminal_checks:
        - git diff --check
        - clean-worktree
        - owned-paths-only
    - lane_id: assignment-recovery
      role: implementation
      display_role: impl
      display_slug: assignment_recovery
      eligible_slots: [P4]
      dependency_wave: 2
      owned_paths:
        - scripts/assign_agent_name.py
        - scripts/test_assign_agent_name.py
        - scripts/scheduler_state.py
        - scripts/test_scheduler_state.py
        - scripts/create_control_state.py
        - scripts/test_create_control_state.py
        - scripts/register_lane.py
        - scripts/test_register_lane.py
        - scripts/write_lane_receipt.py
        - scripts/test_write_lane_receipt.py
        - scripts/validate_lane_receipt.py
        - scripts/test_validate_lane_receipt.py
        - scripts/next_controller_action.py
        - scripts/test_next_controller_action.py
        - scripts/await_receipts.py
        - scripts/test_await_receipts.py
        - scripts/run_watcher.py
        - scripts/test_run_watcher.py
        - scripts/render_agent_status.py
        - scripts/test_render_agent_status.py
      prerequisites: [naming-core]
      acceptance:
        - python3 -B -m unittest scripts.test_assign_agent_name scripts.test_scheduler_state scripts.test_create_control_state scripts.test_register_lane scripts.test_write_lane_receipt scripts.test_validate_lane_receipt scripts.test_next_controller_action scripts.test_await_receipts scripts.test_run_watcher scripts.test_render_agent_status -v
      terminal_checks:
        - git diff --check
        - clean-worktree
        - owned-paths-only
    - lane_id: contract-assets
      role: implementation
      display_role: docs
      display_slug: naming_contract
      eligible_slots: [P2]
      dependency_wave: 3
      owned_paths:
        - SKILL.md
        - README.md
        - references/plan-contract.md
        - references/routing.md
        - references/delivery-flow.md
        - scripts/verify_contract.py
        - scripts/test_p1_contract.py
        - assets/delivery-flow.excalidraw
        - assets/delivery-flow.svg
        - assets/delivery-flow.png
        - assets/manifest.json
        - scripts/verify_assets.py
        - docs/meta-harness/2026-07-29-dynamic-pane-role-names/feedback/skill-red.json
        - docs/meta-harness/2026-07-29-dynamic-pane-role-names/feedback/skill-green.json
      prerequisites:
        - controller-pool
        - assignment-recovery
      acceptance:
        - python3 -B scripts/verify_contract.py
        - python3 -B scripts/verify_assets.py
        - python3 -B scripts/render_assets.py --check assets/delivery-flow.png
        - python3 -B -m unittest scripts.test_p1_contract -v
      terminal_checks:
        - git diff --check
        - clean-worktree
        - owned-paths-only
  reviews:
    P5:
      applicable: true
      role: integration-owner
      responsibilities:
        - integrate accepted worker SHAs
        - run complete deterministic gate
        - install exact accepted runtime package
        - push and verify public release
    P6:
      applicable: true
      role: integration-reviewer
      matrix:
        - identity and request-id stability
        - legacy migration and pool recovery
        - integrated artifact provenance
    P7:
      applicable: true
      role: qc
      matrix:
        - live role visibility
        - rename-before-prompt
        - non-blocking P1 distribution
        - concurrent-space controller isolation
        - post-compaction P1 boundary
        - pane-move recovery
    P8:
      applicable: true
      role: designer
      matrix:
        - original-detail graph review
        - naming legend legibility
        - unchanged Compact and Standard topology
    P9:
      applicable: false
      reason: no persona or RBAC product journey changes
  deployment:
    topology: public-skill-package-and-local-install
    local_target: /Users/haido/.codex/skills/herdr-orchestrator
    public_target: https://github.com/cxzharry/herdr-orchestrator
    verification:
      - installed-copy full script suite
      - installed contract and asset validation
      - exact local and remote release SHA
      - GitHub visibility PUBLIC
  blocking_severity:
    - Critical
    - High
    - Important
  required_evidence:
    - validator-clean current-generation lane receipts
    - RED and GREEN test output per behavior lane
    - exact worker commit SHAs and owned-path proof
    - P5 integration SHA and complete gate output
    - live Herdr agent-list and control-state canary
    - two-space same-socket isolation and post-compaction routing evidence
    - root SKILL word and byte budgets
    - P6, P7, and P8 independent PASS receipts
    - installed tree evidence and recoverable backup path
    - exact origin/main SHA and public visibility
```
