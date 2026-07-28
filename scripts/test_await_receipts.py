import json
import tempfile
import unittest
from pathlib import Path

from scripts.await_receipts import LaneLostError, ReceiptWaitError, await_lanes


def lane_state(receipt_path: Path) -> dict:
    return {
        "schema_version": "herdr-control-state/v1",
        "contract_id": "contract-a",
        "lanes": {
            "schema": {
                "contract_id": "contract-a",
                "lane_id": "schema",
                "generation": 1,
                "role": "worker",
                "agent_name": "hdr_p2",
                "pane_id": "w1:p2",
                "session_id": "session-1",
                "input_identity": {"base_sha": "abc"},
                "receipt_path": str(receipt_path),
            }
        },
    }


def pass_receipt(pane_id: str = "w1:p2") -> dict:
    return {
        "schema_version": "herdr-lane-receipt/v1",
        "contract_id": "contract-a",
        "lane_id": "schema",
        "generation": 1,
        "role": "worker",
        "agent_name": "hdr_p2",
        "pane_id": pane_id,
        "session_id": "session-1",
        "status": "PASS",
        "input_identity": {"base_sha": "abc"},
        "output_identity": {"diff": "def"},
        "covered_acceptance": ["schema"],
        "checks": [{"command": "python -m unittest", "status": "PASS"}],
        "finding_or_blocker": None,
        "resume_condition": None,
    }


class AwaitReceiptsTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.state_path = self.root / "control-state.json"
        self.receipt_path = self.root / "schema-g1.json"
        self.state_path.write_text(
            json.dumps(lane_state(self.receipt_path)),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_returns_as_soon_as_current_receipt_is_validator_clean(self):
        self.receipt_path.write_text(json.dumps(pass_receipt()), encoding="utf-8")

        result = await_lanes(self.state_path, ["schema"], timeout=0.1, poll=0.001)

        self.assertEqual(result["status"], "terminal")
        self.assertEqual(result["lanes"], {"schema": "PASS"})

    def test_finding_is_a_terminal_transition_not_a_timeout(self):
        receipt = pass_receipt()
        receipt["status"] = "FINDING"
        receipt["output_identity"] = {"diff": "def"}
        receipt["covered_acceptance"] = []
        receipt["checks"] = []
        receipt["finding_or_blocker"] = {
            "severity": "High",
            "expected": "immutable",
            "actual": "mutable",
            "evidence_ref": "canary.py:1",
            "suspected_owner": "integration",
        }
        self.receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

        result = await_lanes(self.state_path, ["schema"], timeout=0.1, poll=0.001)

        self.assertEqual(result["lanes"], {"schema": "FINDING"})

    def test_invalid_receipt_fails_immediately(self):
        receipt = pass_receipt()
        receipt["generation"] = 2
        self.receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

        with self.assertRaisesRegex(ReceiptWaitError, "generation"):
            await_lanes(self.state_path, ["schema"], timeout=0.1, poll=0.001)

    def test_rebinds_moved_pane_by_stable_session(self):
        calls = 0

        def live_agents():
            nonlocal calls
            calls += 1
            if calls == 2:
                self.receipt_path.write_text(
                    json.dumps(pass_receipt("w9:p8")),
                    encoding="utf-8",
                )
            return [
                {
                    "name": "hdr_p2",
                    "pane_id": "w9:p8",
                    "agent_session": {"value": "session-1"},
                }
            ]

        result = await_lanes(
            self.state_path,
            ["schema"],
            timeout=0.1,
            poll=0.001,
            live_agents=live_agents,
            liveness_poll=0.001,
        )

        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["lanes"]["schema"]["pane_id"], "w9:p8")
        self.assertEqual(
            result["rebound"]["schema"],
            {"previous_pane_id": "w1:p2", "pane_id": "w9:p8"},
        )

    def test_reports_closed_lane_lost_before_receipt_timeout(self):
        with self.assertRaises(LaneLostError) as caught:
            await_lanes(
                self.state_path,
                ["schema"],
                timeout=1,
                poll=0.001,
                live_agents=lambda: [],
                liveness_poll=0.001,
                missing_checks=2,
            )

        self.assertEqual(
            caught.exception.lost["schema"]["reason"],
            "session_not_live",
        )
        self.assertEqual(
            caught.exception.lost["schema"]["session_id"],
            "session-1",
        )

    def test_terminal_receipt_wins_when_agent_is_already_closed(self):
        self.receipt_path.write_text(json.dumps(pass_receipt()), encoding="utf-8")

        result = await_lanes(
            self.state_path,
            ["schema"],
            timeout=0.1,
            poll=0.001,
            live_agents=lambda: self.fail("liveness must not run"),
        )

        self.assertEqual(result["lanes"], {"schema": "PASS"})


if __name__ == "__main__":
    unittest.main()
