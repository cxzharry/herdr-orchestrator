import json
import tempfile
import unittest
from pathlib import Path

from scripts.create_control_state import StateCreationError, create_state


class CreateControlStateTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.manifest = self.root / "manifest.json"
        self.state = self.root / "run" / "control-state.json"
        self.manifest.write_text(
            json.dumps(
                {
                    "schema_version": "herdr-run-manifest/v1",
                    "contract_id": "contract-a",
                    "root": "/tmp/project",
                    "base_sha": "abc",
                    "approved_input_sha256": "def",
                    "lanes": [
                        {
                            "lane_id": "quality",
                            "generation": 1,
                            "role": "worker",
                            "agent_name": "worker-quality",
                            "pane_id": "w1:p2",
                            "session_id": "session-1",
                            "input_identity": {"base_sha": "abc"},
                            "owned_scope": ["quality.py"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_creates_normalized_state_and_directories(self):
        value = create_state(self.manifest, self.state)

        lane = value["lanes"]["quality"]
        self.assertEqual(value["schema_version"], "herdr-control-state/v2")
        self.assertEqual(value["revision"], 0)
        self.assertEqual(value["requests"], {})
        self.assertEqual(lane["contract_id"], "contract-a")
        self.assertEqual(lane["root"], "/tmp/project")
        self.assertEqual(lane["base_sha"], "abc")
        self.assertEqual(lane["state"], "READY")
        self.assertEqual(
            lane["receipt_path"],
            str(self.state.parent / "receipts" / "quality-g1.json"),
        )
        self.assertTrue((self.state.parent / "receipts").is_dir())
        self.assertTrue((self.state.parent / "evidence").is_dir())

    def test_rejects_duplicate_lanes(self):
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        value["lanes"].append(value["lanes"][0])
        self.manifest.write_text(json.dumps(value), encoding="utf-8")

        with self.assertRaisesRegex(StateCreationError, "duplicate lane"):
            create_state(self.manifest, self.state)

    def test_does_not_overwrite_state(self):
        self.state.parent.mkdir(parents=True)
        self.state.write_text("{}\n", encoding="utf-8")

        with self.assertRaisesRegex(StateCreationError, "already exists"):
            create_state(self.manifest, self.state)


if __name__ == "__main__":
    unittest.main()
