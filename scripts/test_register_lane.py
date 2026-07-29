import json
import tempfile
import unittest
from pathlib import Path

from scripts.register_lane import LaneRegistrationError, register_lane


class RegisterLaneTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.state = Path(self.tempdir.name) / "control-state.json"
        self.state.write_text(
            json.dumps(
                {
                    "contract_id": "contract-a",
                    "lanes": {
                        "integration": {
                            "lane_id": "integration",
                            "generation": 1,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        self.lane = Path(self.tempdir.name) / "review.json"
        self.lane.write_text(
            json.dumps(
                {
                    "lane_id": "review",
                    "generation": 1,
                    "role": "integration-reviewer",
                    "agent_name": "reviewer",
                    "pane_id": "w1:p6",
                    "session_id": "session-6",
                    "input_identity": {"artifact": "abc"},
                    "owned_scope": [],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_registers_live_lane_with_default_receipt_path(self):
        value = register_lane(self.state, self.lane)

        lane = value["lanes"]["review"]
        self.assertEqual(lane["contract_id"], "contract-a")
        self.assertEqual(value["schema_version"], "herdr-control-state/v2")
        self.assertEqual(value["revision"], 1)
        self.assertEqual(lane["state"], "READY")
        self.assertEqual(
            lane["receipt_path"],
            str(self.state.parent / "receipts" / "review-g1.json"),
        )

    def test_rejects_existing_lane(self):
        value = json.loads(self.lane.read_text(encoding="utf-8"))
        value["lane_id"] = "integration"
        self.lane.write_text(json.dumps(value), encoding="utf-8")

        with self.assertRaisesRegex(LaneRegistrationError, "already exists"):
            register_lane(self.state, self.lane)


if __name__ == "__main__":
    unittest.main()
