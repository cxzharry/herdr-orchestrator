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
                    "controller_scope": "scope-a",
                    "root": "/tmp/project",
                    "base_sha": "abc",
                    "approved_input_sha256": "def",
                    "lanes": [
                        {
                            "lane_id": "quality",
                            "generation": 1,
                            "slot": "P2",
                            "role": "worker",
                            "display_role": "impl",
                            "display_slug": "quality-check",
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
        self.assertEqual(lane["controller_scope"], "scope-a")
        self.assertEqual(lane["slot"], "P2")
        self.assertEqual(lane["display_role"], "impl")
        self.assertEqual(lane["display_slug"], "quality-check")
        self.assertEqual(lane["expected_agent_name"], "worker-quality")
        self.assertEqual(lane["dispatch_agent_name"], "worker-quality")
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

    def test_requires_controller_scope_for_new_state(self):
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        del value["controller_scope"]
        self.manifest.write_text(json.dumps(value), encoding="utf-8")

        with self.assertRaisesRegex(StateCreationError, "controller_scope"):
            create_state(self.manifest, self.state)

    def test_copies_gate_matrix_to_control_state(self):
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        value["gate_matrix"] = {
            "mode": "Standard",
            "applicable": {"P5": True, "P6": True, "P7": False, "P8": True},
        }
        self.manifest.write_text(json.dumps(value), encoding="utf-8")

        created = create_state(self.manifest, self.state)

        self.assertEqual(created["gate_matrix"], value["gate_matrix"])

    def test_rejects_lane_leased_to_different_scope(self):
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        value["lanes"][0]["controller_scope"] = "scope-b"
        self.manifest.write_text(json.dumps(value), encoding="utf-8")

        with self.assertRaisesRegex(StateCreationError, "different controller scope"):
            create_state(self.manifest, self.state)


if __name__ == "__main__":
    unittest.main()
