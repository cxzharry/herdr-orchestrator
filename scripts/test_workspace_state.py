import tempfile
import unittest
from pathlib import Path

from scripts.workspace_state import (
    StateError,
    create_state,
    initial_state,
    load_state,
    mutate_state,
    register_lane,
    transition_lane,
)


class WorkspaceStateTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
