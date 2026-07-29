import json
import tempfile
import unittest
from pathlib import Path

from scripts.write_lane_receipt import ReceiptWriteError, write_receipt


class WriteLaneReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.receipt = self.root / "receipts" / "quality-g1.json"
        self.state = self.root / "control-state.json"
        self.state.write_text(
            json.dumps(
                {
                    "contract_id": "contract-a",
                    "root": "/tmp/project",
                    "lanes": {
                        "quality": {
                            "generation": 1,
                            "role": "worker",
                            "agent_name": "p2_impl_quality",
                            "expected_agent_name": "p2_impl_quality",
                            "dispatch_agent_name": "hdr_p2",
                            "pane_id": "w1:p2",
                            "session_id": "session-1",
                            "input_identity": {"base_sha": "abc"},
                            "receipt_path": str(self.receipt),
                        },
                        "review": {
                            "generation": 1,
                            "role": "integration-reviewer",
                            "agent_name": "reviewer",
                            "pane_id": "w1:p3",
                            "session_id": "session-2",
                            "input_identity": {"artifact": "def"},
                            "receipt_path": str(
                                self.root / "receipts" / "review-g1.json"
                            ),
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_writes_validator_clean_pass_from_live_identity(self):
        value = write_receipt(
            self.state,
            "quality",
            "PASS",
            output_identity={"diff_sha256": "123"},
            covered_acceptance=["quality accepts threshold equality"],
            checks=[{"command": "python3 -m unittest", "result": "pass"}],
        )

        self.assertEqual(value["input_identity"], {"base_sha": "abc"})
        self.assertEqual(value["agent_name"], "hdr_p2")
        self.assertIsNone(value["finding_or_blocker"])
        self.assertIsNone(value["resume_condition"])
        self.assertTrue(self.receipt.is_file())

    def test_reviewer_output_defaults_to_exact_input(self):
        value = write_receipt(
            self.state,
            "review",
            "PASS",
            output_identity=None,
            covered_acceptance=["artifact independently reviewed"],
            checks=[{"command": "python3 probe.py", "result": "pass"}],
        )

        self.assertEqual(value["output_identity"], {"artifact": "def"})

    def test_rejects_invalid_pass_before_write(self):
        with self.assertRaisesRegex(ReceiptWriteError, "PASS requires checks"):
            write_receipt(
                self.state,
                "quality",
                "PASS",
                output_identity={"diff_sha256": "123"},
                covered_acceptance=["quality checked"],
                checks=[],
            )
        self.assertFalse(self.receipt.exists())


if __name__ == "__main__":
    unittest.main()
