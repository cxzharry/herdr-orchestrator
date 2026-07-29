import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_watcher import (
    FakeClock,
    append_watcher_failure,
    reconcile_once,
    run_watcher,
    signal_idle_p1,
)


def control_state(root: Path) -> dict:
    return {
        "schema_version": "herdr-control-state/v1",
        "contract_id": "contract-a",
        "run_id": "run-a",
        "controller_scope": "scope-a",
        "controller": {
            "agent_name": "p1_orchestrator_a1b2",
            "controller_scope": "scope-a",
            "session_id": "p1-session",
            "status": "idle",
        },
        "lanes": {
            "lane-a": lane(root, "lane-a", "hdr_p2", "w1:p2", "s-a"),
            "lane-b": lane(root, "lane-b", "hdr_p3", "w1:p3", "s-b"),
        },
        "watcher_events": [],
    }


def lane(root: Path, lane_id: str, agent: str, pane: str, session: str) -> dict:
    return {
        "contract_id": "contract-a",
        "lane_id": lane_id,
        "generation": 1,
        "role": "worker",
        "agent_name": agent,
        "expected_agent_name": agent,
        "dispatch_agent_name": agent,
        "slot": "P" + pane.rsplit(":p", 1)[1],
        "pane_id": pane,
        "session_id": session,
        "input_identity": {"base_sha": "abc", "lane": lane_id},
        "receipt_path": str(root / f"{lane_id}.json"),
    }


def receipt(state: dict, lane_id: str, status: str = "PASS") -> dict:
    lane_value = state["lanes"][lane_id]
    return {
        "schema_version": "herdr-lane-receipt/v1",
        "contract_id": state["contract_id"],
        "lane_id": lane_id,
        "generation": lane_value["generation"],
        "role": lane_value["role"],
        "agent_name": lane_value["agent_name"],
        "pane_id": lane_value["pane_id"],
        "session_id": lane_value["session_id"],
        "status": status,
        "input_identity": lane_value["input_identity"],
        "output_identity": {"lane_sha": "def"},
        "covered_acceptance": ["watcher"],
        "checks": [{"command": "unit", "result": "pass"}],
        "finding_or_blocker": None,
        "resume_condition": None,
    }


def live_agent(name: str, pane: str, session: str, status: str = "done") -> dict:
    return {
        "name": name,
        "pane_id": pane,
        "agent_status": status,
        "agent_session": {"value": session},
    }


class FakeHerdr:
    def __init__(self):
        self.prompts = []

    def prompt_agent(self, agent_name: str, message: str):
        self.prompts.append((agent_name, message))


class RunWatcherTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.state_path = self.root / "control-state.json"
        self.state = control_state(self.root)
        self.state_path.write_text(json.dumps(self.state), encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def events(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))[
            "watcher_events"
        ]

    def test_appends_receipt_event_once_for_terminal_receipt(self):
        Path(self.state["lanes"]["lane-a"]["receipt_path"]).write_text(
            json.dumps(receipt(self.state, "lane-a")),
            encoding="utf-8",
        )

        first = reconcile_once(self.state_path, live_agents=[])
        second = reconcile_once(self.state_path, live_agents=[])

        self.assertEqual([event["type"] for event in first], ["RECEIPT"])
        self.assertEqual(second, [])
        self.assertEqual(len(self.events()), 1)
        self.assertEqual(self.events()[0]["lane_id"], "lane-a")

    def test_appends_move_event_without_rebinding_control_state(self):
        events = reconcile_once(
            self.state_path,
            live_agents=[live_agent("hdr_p2", "w9:p8", "s-a")],
        )

        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["lanes"]["lane-a"]["pane_id"], "w1:p2")
        self.assertEqual(events[0]["type"], "LANE_MOVED")
        self.assertEqual(events[0]["previous_pane_id"], "w1:p2")
        self.assertEqual(events[0]["pane_id"], "w9:p8")

    def test_appends_loss_event_after_bounded_missing_checks(self):
        first = reconcile_once(
            self.state_path,
            live_agents=[live_agent("hdr_p3", "w1:p3", "s-b")],
            missing_checks=2,
        )
        second = reconcile_once(
            self.state_path,
            live_agents=[live_agent("hdr_p3", "w1:p3", "s-b")],
            missing_checks=2,
        )

        self.assertEqual(first, [])
        self.assertEqual([event["type"] for event in second], ["LANE_LOST"])
        self.assertEqual(self.events()[0]["session_id"], "s-a")

    def test_duplicate_event_ids_are_idempotent(self):
        Path(self.state["lanes"]["lane-a"]["receipt_path"]).write_text(
            json.dumps(receipt(self.state, "lane-a")),
            encoding="utf-8",
        )

        reconcile_once(self.state_path, live_agents=[])
        reconcile_once(self.state_path, live_agents=[])

        event_ids = [event["event_id"] for event in self.events()]
        self.assertEqual(len(event_ids), len(set(event_ids)))

    def test_safe_signal_sends_only_event_id_when_p1_idle(self):
        adapter = FakeHerdr()
        event = {
            "event_id": "evt_abc",
            "type": "RECEIPT",
            "lane_id": "lane-a",
        }

        sent = signal_idle_p1(self.state_path, event, adapter)

        self.assertTrue(sent)
        self.assertEqual(adapter.prompts, [("p1_orchestrator_a1b2", "HERDR_EVENT evt_abc")])

    def test_busy_p1_keeps_event_queued_without_prompt(self):
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state["controller"]["status"] = "working"
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        adapter = FakeHerdr()

        sent = signal_idle_p1(
            self.state_path,
            {"event_id": "evt_busy", "type": "RECEIPT"},
            adapter,
        )

        self.assertFalse(sent)
        self.assertEqual(adapter.prompts, [])

    def test_terminal_exit_after_all_lanes_have_terminal_events(self):
        for lane_id in ("lane-a", "lane-b"):
            Path(self.state["lanes"][lane_id]["receipt_path"]).write_text(
                json.dumps(receipt(self.state, lane_id)),
                encoding="utf-8",
            )

        result = run_watcher(
            self.state_path,
            live_agents=lambda: [],
            adapter=FakeHerdr(),
            clock=FakeClock(),
            poll=0,
            max_ticks=3,
        )

        self.assertEqual(result["status"], "terminal")
        self.assertEqual(result["events"], 2)

    def test_watcher_failure_event_is_immutable_and_idempotent(self):
        first = append_watcher_failure(self.state_path, "boom")
        second = append_watcher_failure(self.state_path, "boom")

        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(len(self.events()), 1)
        self.assertEqual(self.events()[0]["type"], "WATCHER_FAILURE")

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

    def test_scope_a_signal_never_targets_scope_b_controller(self):
        self.state["live_controllers"] = [
            {"agent_name": "p1_orchestrator_b2", "controller_scope": "scope-b"},
        ]
        self.state_path.write_text(json.dumps(self.state), encoding="utf-8")
        adapter = FakeHerdr()

        signal_idle_p1(
            self.state_path,
            {"event_id": "evt_scope", "type": "LANE_NAME_DRIFT"},
            adapter,
        )

        self.assertEqual(adapter.prompts, [("p1_orchestrator_a1b2", "HERDR_EVENT evt_scope")])


if __name__ == "__main__":
    unittest.main()
