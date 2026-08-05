import copy
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
                    "workspace_id": "w1",
                    "mode": "Compact",
                    "risk": {
                        "local": True,
                        "low_risk": True,
                        "path_owned": True,
                        "deterministic_acceptance": True,
                    },
                    "review_applicability": {
                        "P7": False,
                        "P8": False,
                        "P9": False,
                    },
                    "lanes": [
                        {
                            "lane_id": "quality",
                            "generation": 1,
                            "role": "implementation",
                            "agent_name": "worker-quality",
                            "pane_id": "w1:p2",
                            "session_id": "session-1",
                            "input_identity": {"base_sha": "abc"},
                            "owned_scope": ["quality.py"],
                        },
                        {
                            "lane_id": "integration",
                            "generation": 1,
                            "role": "integration",
                            "agent_name": "p5_integration",
                            "pane_id": "w1:p5",
                            "session_id": "session-5",
                            "input_identity": {"candidate_commit": "pending"},
                            "owned_scope": [],
                        },
                        {
                            "lane_id": "independent_review",
                            "generation": 1,
                            "role": "integration-reviewer",
                            "agent_name": "p6_review",
                            "pane_id": "w1:p6",
                            "session_id": "session-6",
                            "input_identity": {"candidate_commit": "pending"},
                            "owned_scope": [],
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
        self.assertEqual(value["schema_version"], "herdr-workspace-state/v1")
        self.assertEqual(value["workspace_id"], "w1")
        self.assertEqual(value["revision"], 0)
        self.assertEqual(value["requests"], {})
        self.assertEqual(value["run"].get("mode"), "Compact")
        self.assertEqual(
            value["run"].get("risk"),
            json.loads(self.manifest.read_text(encoding="utf-8"))["risk"],
        )
        self.assertEqual(
            value["run"].get("review_applicability"),
            {"P7": False, "P8": False, "P9": False},
        )
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

    def test_compact_counts_only_implementation_lanes(self):
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        roles = (
            "implementation",
            "implementation",
            "functional-qc",
            "persona-qc",
        )
        for index, role in enumerate(roles, start=2):
            lane = dict(value["lanes"][0])
            lane.update(
                {
                    "lane_id": f"lane-{index}",
                    "role": role,
                    "agent_name": f"worker-{index}",
                    "pane_id": f"w1:p{index}",
                    "session_id": f"session-{index}",
                    "owned_scope": (
                        [f"file-{index}.py"] if role == "implementation" else []
                    ),
                }
            )
            value["lanes"].append(lane)
        self.manifest.write_text(json.dumps(value), encoding="utf-8")

        created = create_state(self.manifest, self.state)

        self.assertEqual(created["run"]["mode"], "Compact")

    def test_rejects_missing_p5_or_p6_lane_for_both_modes(self):
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        required_roles = {
            "integration": "P5 integration",
            "integration-reviewer": "P6 independent-review",
        }
        for mode in ("Compact", "Standard"):
            for role, label in required_roles.items():
                with self.subTest(mode=mode, role=role):
                    value = copy.deepcopy(manifest)
                    value["mode"] = mode
                    if mode == "Standard":
                        value["risk"]["high_assurance"] = True
                    value["lanes"] = [
                        lane for lane in value["lanes"] if lane["role"] != role
                    ]
                    self.manifest.write_text(json.dumps(value), encoding="utf-8")
                    state = self.root / f"run-{mode}-{role}" / "control-state.json"

                    with self.assertRaisesRegex(StateCreationError, label):
                        create_state(self.manifest, state)

                    self.assertFalse(state.parent.exists())

    def test_rejects_duplicate_mandatory_roles_before_creating_directories(self):
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        for role in ("integration", "integration-reviewer"):
            with self.subTest(role=role):
                value = copy.deepcopy(manifest)
                lane = next(item for item in value["lanes"] if item["role"] == role)
                duplicate = dict(lane)
                duplicate["lane_id"] = f"duplicate-{role}"
                value["lanes"].append(duplicate)
                self.manifest.write_text(json.dumps(value), encoding="utf-8")
                state = self.root / f"run-duplicate-{role}" / "control-state.json"

                with self.assertRaisesRegex(StateCreationError, "exactly one"):
                    create_state(self.manifest, state)

                self.assertFalse(state.parent.exists())

    def test_rejects_missing_mode_contract_fields_before_creating_directories(self):
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        for field in ("mode", "risk", "review_applicability"):
            with self.subTest(field=field):
                value = dict(manifest)
                del value[field]
                self.manifest.write_text(json.dumps(value), encoding="utf-8")
                state = self.root / f"run-{field}" / "control-state.json"

                with self.assertRaisesRegex(StateCreationError, field):
                    create_state(self.manifest, state)

                self.assertFalse(state.parent.exists())

    def test_rejects_contradictory_compact_mode_before_creating_directories(self):
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        value["risk"]["browser_or_visual"] = True
        self.manifest.write_text(json.dumps(value), encoding="utf-8")

        with self.assertRaisesRegex(StateCreationError, "requires Standard"):
            create_state(self.manifest, self.state)

        self.assertFalse(self.state.parent.exists())

    def test_rejects_compact_review_applicability_before_creating_directories(self):
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        value["review_applicability"]["P9"] = True
        self.manifest.write_text(json.dumps(value), encoding="utf-8")

        with self.assertRaisesRegex(StateCreationError, "Compact cannot require"):
            create_state(self.manifest, self.state)

        self.assertFalse(self.state.parent.exists())

    def test_does_not_overwrite_state(self):
        self.state.parent.mkdir(parents=True)
        self.state.write_text("{}\n", encoding="utf-8")

        with self.assertRaisesRegex(StateCreationError, "already exists"):
            create_state(self.manifest, self.state)


if __name__ == "__main__":
    unittest.main()
