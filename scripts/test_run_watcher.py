import tempfile
import unittest
from pathlib import Path

from scripts.run_watcher import (
    FakeClock,
    acquire_watcher,
    observe_once,
    run_once,
    run_watcher,
    verify_wake_path,
)
from scripts.workspace_state import create_state, load_state


def live_agent(name="p2_impl", pane="w6:p2", session="s-a", status="done"):
    return {
        "name": name,
        "pane_id": pane,
        "workspace_id": "w6",
        "agent_status": status,
        "agent_session": {"value": session},
    }


class WorkspaceWatcherAdapter:
    def __init__(self, agents=None):
        self.agents = list(agents or [])
        self.signals = []

    def list_agents(self):
        return list(self.agents)

    def signal_agent(self, agent_name: str, message: str):
        self.signals.append(agent_name)


class RunWatcherTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.path = self.root / "workspace-state.json"
        create_state(
            self.path,
            "w6",
            controller={"role_name": "p1_orchestrator", "session_id": "p1-a"},
            lanes=[
                {
                    "lane_id": "lane-a",
                    "generation": 1,
                    "state": "ACTIVE",
                    "session_id": "s-a",
                    "pane_id": "w6:p2",
                }
            ],
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_observe_once_reports_missing_lane_without_mutating_state(self):
        before = load_state(self.path)

        observation = observe_once(before, live_agents=[], receipt_paths={}, now=100)

        self.assertEqual("LANE_MISSING", observation["events"][0]["kind"])
        self.assertEqual(before, load_state(self.path))

    def test_watcher_only_appends_observations(self):
        before = load_state(self.path)

        run_once(self.path, WorkspaceWatcherAdapter(), now=100)

        after = load_state(self.path)
        self.assertEqual(before["lanes"], after["lanes"])
        self.assertEqual(before["queues"], after["queues"])
        self.assertTrue(after["events"])
        self.assertEqual(100, after["watcher"]["heartbeat_at"])

    def test_one_watcher_per_workspace_controller_lifecycle(self):
        first = acquire_watcher(self.path, "watcher-a", controller_session="p1-a")
        second = acquire_watcher(self.path, "watcher-b", controller_session="p1-a")

        self.assertTrue(first)
        self.assertFalse(second)

    def test_actionable_event_is_persisted_before_p1_signal(self):
        adapter = WorkspaceWatcherAdapter()

        run_once(self.path, adapter, now=100)

        self.assertTrue(load_state(self.path)["events"])
        self.assertEqual(["p1_orchestrator"], adapter.signals)

    def test_duplicate_events_are_idempotent(self):
        adapter = WorkspaceWatcherAdapter()

        run_once(self.path, adapter, now=100)
        run_once(self.path, adapter, now=101)

        events = load_state(self.path)["events"]
        event_ids = [event["event_id"] for event in events]
        self.assertEqual(len(event_ids), len(set(event_ids)))

    def test_receipt_event_uses_artifact_identity(self):
        receipt_path = self.root / "lane-a-g1.json"
        receipt_path.write_text("{}", encoding="utf-8")
        state = load_state(self.path)
        state["lanes"]["lane-a"]["receipt_path"] = str(receipt_path)

        observation = observe_once(
            state,
            live_agents=[live_agent()],
            receipt_paths={"lane-a": str(receipt_path)},
            now=100,
        )

        self.assertEqual("RECEIPT_PRESENT", observation["events"][0]["kind"])
        self.assertEqual(str(receipt_path), observation["events"][0]["artifact"])

    def test_verify_wake_path_sets_proof_only_after_cursor_advances(self):
        adapter = WorkspaceWatcherAdapter()

        verified = verify_wake_path(
            self.path,
            adapter,
            now=100,
            advanced_cursor=lambda: load_state(self.path)["event_cursor"],
        )

        self.assertTrue(verified)
        self.assertEqual(100, load_state(self.path)["watcher"]["wake_verified_at"])
        self.assertEqual(["p1_orchestrator"], adapter.signals)

    def test_run_watcher_is_bounded_by_max_ticks(self):
        result = run_watcher(
            self.path,
            adapter=WorkspaceWatcherAdapter(),
            clock=FakeClock(),
            poll=0,
            max_ticks=3,
        )

        self.assertEqual({"status": "running", "ticks": 3, "events": 3}, result)


if __name__ == "__main__":
    unittest.main()
