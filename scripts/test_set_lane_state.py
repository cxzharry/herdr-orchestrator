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
                    "contract_id": "contract-a",
                    "lanes": {
                        "quality": {
                            "generation": 2,
                            "state": "ACCEPTED",
                            "receipt_path": "quality-g2.json",
                            "input_identity": {"base_sha": "abc"},
                        },
                        "integration": {
                            "generation": 2,
                            "state": "ACCEPTED",
                            "receipt_path": "integration-g2.json",
                            "input_identity": {"base_sha": "abc"},
                        },
                    },
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
            generation=3,
            state_value="ACTIVE",
            receipt_path="integration-g3.json",
            input_updates={"finding_sha256": "def"},
        )

        state = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(state["lanes"]["quality"]["generation"], 2)
        self.assertEqual(state["lanes"]["integration"]["generation"], 3)
        self.assertEqual(
            state["lanes"]["integration"]["input_identity"]["finding_sha256"],
            "def",
        )

    def test_rejects_unknown_lane(self):
        with self.assertRaisesRegex(StateUpdateError, "unknown lane"):
            set_lane(self.path, "schema", 1, "ACTIVE", "schema-g1.json", {})


if __name__ == "__main__":
    unittest.main()
