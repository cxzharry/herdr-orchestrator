import json
import tempfile
import threading
import unittest
from pathlib import Path

from scripts.scheduler_state import (
    classify_delta,
    register_delta,
    read_state,
    set_lane,
)


def lane(lane_id, *, state="READY", owned_scope=None, generation=1):
    return {
        "lane_id": lane_id,
        "generation": generation,
        "slot": "P4",
        "role": "worker",
        "display_role": "impl",
        "display_slug": lane_id,
        "agent_name": f"agent-{lane_id}",
        "expected_agent_name": f"agent-{lane_id}",
        "dispatch_agent_name": f"agent-{lane_id}",
        "pane_id": f"w1:{lane_id}",
        "session_id": f"session-{lane_id}",
        "input_identity": {"base_sha": "abc123"},
        "owned_scope": owned_scope or [],
        "state": state,
        "receipt_path": f"{lane_id}-g{generation}.json",
    }


class SchedulerStateTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.state_path = self.root / "control-state.json"
        self.state_path.write_text(
            json.dumps(
                {
                    "schema_version": "herdr-control-state/v2",
                    "contract_id": "contract-a",
                    "controller_scope": "scope-a",
                    "root": "/tmp/project",
                    "base_sha": "abc123",
                    "approved_input_sha256": "input123",
                    "revision": 0,
                    "controller": {"lane_id": "p1", "session_id": "session-p1"},
                    "requests": {},
                    "request_order": [],
                    "event_cursor": 0,
                    "watcher": {"session_id": "watcher-1"},
                    "lanes": {
                        "p2": lane("p2", state="ACTIVE", owned_scope=["scripts/scheduler_state.py"]),
                        "p3": lane("p3", state="ACTIVE", owned_scope=["scripts/run_watcher.py"]),
                        "p4": lane("p4"),
                    },
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def request(self, request_id, paths, **overrides):
        value = {
            "request_id": request_id,
            "summary": "change request",
            "change_type": "code",
            "affected_paths": paths,
            "input_identity": {"request_sha256": request_id},
            "dependencies": [],
        }
        value.update(overrides)
        return value

    def test_disjoint_delta_dispatches_to_idle_lane(self):
        result = register_delta(
            self.state_path,
            self.request(
                "req-disjoint",
                ["scripts/controller_router.py"],
                display_role="impl",
                display_slug="auth",
            ),
        )

        state = read_state(self.state_path)
        self.assertEqual(result["status"], "DISPATCH")
        self.assertEqual(result["lane_id"], "p4")
        self.assertEqual(state["lanes"]["p4"]["state"], "ACTIVE")
        self.assertEqual(state["lanes"]["p4"]["owned_scope"], ["scripts/controller_router.py"])
        self.assertEqual(state["lanes"]["p4"]["display_role"], "impl")
        self.assertEqual(state["lanes"]["p4"]["display_slug"], "auth")
        self.assertEqual(state["requests"]["req-disjoint"]["state"], "ACTIVE")
        self.assertEqual(state["revision"], 1)

    def test_overlapping_delta_queues_behind_owner(self):
        result = register_delta(
            self.state_path,
            self.request("req-overlap", ["scripts/scheduler_state.py"]),
        )

        state = read_state(self.state_path)
        self.assertEqual(result["status"], "DEPENDENCY_BLOCKED")
        self.assertEqual(result["blocked_by"], ["p2"])
        self.assertEqual(state["requests"]["req-overlap"]["state"], "DEPENDENCY_BLOCKED")
        self.assertEqual(state["requests"]["req-overlap"]["blocked_by"], ["p2"])

    def test_unknown_paths_produce_analysis_work(self):
        result = register_delta(
            self.state_path,
            self.request("req-unknown", None),
        )

        state = read_state(self.state_path)
        self.assertEqual(result["status"], "ANALYSIS_REQUIRED")
        self.assertEqual(state["requests"]["req-unknown"]["state"], "ANALYSIS_REQUIRED")
        self.assertEqual(state["requests"]["req-unknown"]["analysis_only"], True)

    def test_full_capacity_returns_without_waiting(self):
        state = read_state(self.state_path)
        state["lanes"]["p4"]["state"] = "ACTIVE"
        state["lanes"]["p4"]["owned_scope"] = ["scripts/other.py"]
        self.state_path.write_text(json.dumps(state), encoding="utf-8")

        result = register_delta(
            self.state_path,
            self.request("req-capacity", ["scripts/new_helper.py"]),
        )

        state = read_state(self.state_path)
        self.assertEqual(result["status"], "CAPACITY_BLOCKED")
        self.assertEqual(state["requests"]["req-capacity"]["state"], "CAPACITY_BLOCKED")

    def test_plan_required_classification_does_not_stop_active_lanes(self):
        result = register_delta(
            self.state_path,
            self.request(
                "req-plan",
                ["scripts/scheduler_state.py"],
                change_type="schema",
            ),
        )

        state = read_state(self.state_path)
        self.assertEqual(result["status"], "PLAN_REQUIRED")
        self.assertEqual(state["requests"]["req-plan"]["state"], "PLAN_REQUIRED")
        self.assertEqual(state["lanes"]["p2"]["state"], "ACTIVE")

    def test_request_id_is_idempotent(self):
        first = register_delta(
            self.state_path,
            self.request("req-stable", ["scripts/controller_router.py"]),
        )
        second = register_delta(
            self.state_path,
            self.request("req-stable", ["scripts/controller_router.py"]),
        )

        state = read_state(self.state_path)
        self.assertEqual(second, first)
        self.assertEqual(state["request_order"], ["req-stable"])
        self.assertEqual(state["revision"], 1)

    def test_v1_read_upgrades_to_v2_shape(self):
        self.state_path.write_text(
            json.dumps(
                {
                    "schema_version": "herdr-control-state/v1",
                    "contract_id": "contract-a",
                    "controller_scope": "scope-a",
                    "root": "/tmp/project",
                    "base_sha": "abc123",
                    "approved_input_sha256": "input123",
                    "lanes": {"p4": lane("p4")},
                }
            ),
            encoding="utf-8",
        )

        state = read_state(self.state_path)
        self.assertEqual(state["schema_version"], "herdr-control-state/v2")
        self.assertEqual(state["revision"], 0)
        self.assertEqual(state["requests"], {})
        self.assertEqual(state["request_order"], [])
        self.assertEqual(state["event_cursor"], 0)
        self.assertEqual(state["lanes"]["p4"]["slot"], "P4")
        self.assertEqual(state["lanes"]["p4"]["display_role"], "impl")
        self.assertEqual(state["lanes"]["p4"]["display_slug"], "p4")
        self.assertEqual(state["lanes"]["p4"]["dispatch_agent_name"], "agent-p4")

    def test_lane_generation_identity_is_preserved_on_set(self):
        updated = set_lane(
            self.state_path,
            "p4",
            generation=2,
            state_value="ACTIVE",
            receipt_path="p4-g2.json",
            input_updates={"request_sha256": "req-new"},
            owned_scope=["scripts/new_helper.py"],
        )

        state = read_state(self.state_path)
        self.assertEqual(updated["contract_id"], "contract-a")
        self.assertEqual(updated["root"], "/tmp/project")
        self.assertEqual(updated["base_sha"], "abc123")
        self.assertEqual(updated["generation"], 2)
        self.assertEqual(updated["owned_scope"], ["scripts/new_helper.py"])
        self.assertEqual(state["revision"], 1)

    def test_dependencies_block_until_prerequisite_terminal(self):
        result = register_delta(
            self.state_path,
            self.request(
                "req-dependent",
                ["scripts/dependent.py"],
                dependencies=["p2"],
            ),
        )

        self.assertEqual(result["status"], "DEPENDENCY_BLOCKED")
        self.assertEqual(result["blocked_by"], ["p2"])

    def test_concurrent_updates_do_not_lose_writes(self):
        def update_lane(lane_id):
            set_lane(
                self.state_path,
                lane_id,
                generation=2,
                state_value="ACTIVE",
                receipt_path=f"{lane_id}-g2.json",
                input_updates={f"{lane_id}_sha256": "updated"},
                owned_scope=[f"scripts/{lane_id}.py"],
            )

        threads = [threading.Thread(target=update_lane, args=(lane_id,)) for lane_id in ("p2", "p3")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        state = read_state(self.state_path)
        self.assertEqual(state["lanes"]["p2"]["generation"], 2)
        self.assertEqual(state["lanes"]["p3"]["generation"], 2)
        self.assertEqual(state["lanes"]["p2"]["input_identity"]["p2_sha256"], "updated")
        self.assertEqual(state["lanes"]["p3"]["input_identity"]["p3_sha256"], "updated")
        self.assertEqual(state["revision"], 2)

    def test_classification_marks_public_contract_as_plan_required(self):
        self.assertEqual(
            classify_delta({"change_type": "public_contract", "affected_paths": ["README.md"]}),
            "PLAN_REQUIRED",
        )

    def test_set_lane_rejects_pending_name_assignment(self):
        state = read_state(self.state_path)
        state["lanes"]["p4"]["name_assignment"] = {"token": "token-a"}
        self.state_path.write_text(json.dumps(state), encoding="utf-8")

        with self.assertRaisesRegex(Exception, "pending name assignment"):
            set_lane(
                self.state_path,
                "p4",
                generation=2,
                state_value="ACTIVE",
                receipt_path="p4-g2.json",
                input_updates={},
            )

    def test_register_delta_skips_reserved_lane_and_dispatches_unrelated_lane(self):
        state = read_state(self.state_path)
        state["lanes"]["p3"]["state"] = "READY"
        state["lanes"]["p3"]["owned_scope"] = []
        state["lanes"]["p3"]["name_assignment"] = {"token": "token-a"}
        self.state_path.write_text(json.dumps(state), encoding="utf-8")

        result = register_delta(
            self.state_path,
            self.request("req-other", ["scripts/new_helper.py"]),
        )

        saved = read_state(self.state_path)
        self.assertEqual(result["status"], "DISPATCH")
        self.assertEqual(result["lane_id"], "p4")
        self.assertEqual(saved["lanes"]["p3"]["state"], "READY")

    def test_register_delta_preserves_role_only_display_slug_null(self):
        state = read_state(self.state_path)
        state["lanes"]["p4"]["display_slug"] = "previous"
        self.state_path.write_text(json.dumps(state), encoding="utf-8")

        register_delta(
            self.state_path,
            self.request(
                "req-role-only",
                ["scripts/controller_router.py"],
                display_role="integration_review",
                display_slug=None,
            ),
        )

        lane_value = read_state(self.state_path)["lanes"]["p4"]
        self.assertEqual(lane_value["display_role"], "integration_review")
        self.assertIsNone(lane_value["display_slug"])


if __name__ == "__main__":
    unittest.main()
