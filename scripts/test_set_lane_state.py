import json
import tempfile
import unittest
from pathlib import Path

from scripts.set_lane_state import StateUpdateError, set_lane


class SetLaneStateTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "state.json"
        self.path.write_text(
            json.dumps(
                {
                    "schema_version": "herdr-workspace-state/v1",
                    "workspace_id": "w1",
                    "revision": 0,
                    "controller": {},
                    "slots": {},
                    "run": {
                        "contract_id": "contract-a",
                        "root": "/tmp/project",
                        "base_sha": "abc",
                    },
                    "lanes": {
                        "quality": {
                            "lane_id": "quality",
                            "contract_id": "contract-a",
                            "generation": 2,
                            "state": "ACCEPTED",
                            "receipt_path": "quality-g2.json",
                            "input_identity": {"base_sha": "abc"},
                        },
                        "integration": {
                            "lane_id": "integration",
                            "contract_id": "contract-a",
                            "generation": 2,
                            "state": "ACCEPTED",
                            "receipt_path": "integration-g2.json",
                            "input_identity": {"base_sha": "abc"},
                        },
                    },
                    "requests": {},
                    "request_order": [],
                    "inbox": [],
                    "queues": {"ownership": [], "capacity": []},
                    "watcher": {},
                    "events": [],
                    "event_cursor": 0,
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_updates_only_the_named_lane(self):
        set_lane(
            self.path,
            "integration",
            generation=2,
            state_value="ACTIVE",
            receipt_path="integration-g3.json",
            input_updates={"finding_sha256": "def"},
        )

        state = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(state["lanes"]["quality"]["generation"], 2)
        self.assertEqual(state["lanes"]["integration"]["generation"], 2)
        self.assertEqual(state["revision"], 1)
        self.assertEqual(
            state["lanes"]["integration"]["input_identity"]["finding_sha256"],
            "def",
        )

    def test_rejects_stale_generation(self):
        with self.assertRaisesRegex(StateUpdateError, "generation"):
            set_lane(self.path, "integration", 1, "ACTIVE", "integration-g1.json", {})

    def test_rejects_unknown_lane(self):
        with self.assertRaisesRegex(StateUpdateError, "unknown lane"):
            set_lane(self.path, "schema", 1, "ACTIVE", "schema-g1.json", {})


if __name__ == "__main__":
    unittest.main()
