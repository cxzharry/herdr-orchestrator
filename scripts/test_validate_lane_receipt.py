import copy
import unittest

from scripts.validate_lane_receipt import validate_receipt


class ReceiptValidationTests(unittest.TestCase):
    def setUp(self):
        self.state = {
            "contract_id": "contract-1",
            "artifact_generation": 3,
            "lanes": {
                "lane-api": {
                    "generation": 2,
                    "role": "worker",
                    "agent_name": "worker_api",
                    "pane_id": "w1:p2",
                    "session_id": "session-2",
                    "input_identity": {"base_sha": "abc123"},
                }
            },
        }
        self.receipt = {
            "schema_version": "herdr-lane-receipt/v1",
            "contract_id": "contract-1",
            "lane_id": "lane-api",
            "generation": 2,
            "role": "worker",
            "agent_name": "worker_api",
            "pane_id": "w1:p2",
            "session_id": "session-2",
            "status": "PASS",
            "input_identity": {"base_sha": "abc123"},
            "output_identity": {"lane_sha": "def456"},
            "covered_acceptance": ["API returns the approved response"],
            "checks": [
                {
                    "kind": "command",
                    "value": "pytest tests/test_api.py -q",
                    "result": "pass",
                    "evidence_ref": "evidence/api-test.txt",
                }
            ],
            "finding_or_blocker": None,
            "resume_condition": None,
        }

    def test_accepts_current_worker_pass(self):
        self.assertEqual(validate_receipt(self.receipt, self.state), [])

    def test_rejects_missing_required_field(self):
        receipt = copy.deepcopy(self.receipt)
        del receipt["contract_id"]
        self.assertIn(
            "missing field: contract_id",
            validate_receipt(receipt, self.state),
        )

    def test_rejects_stale_generation(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["generation"] = 1
        self.assertIn(
            "generation does not match current lane",
            validate_receipt(receipt, self.state),
        )

    def test_rejects_cross_contract_receipt(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["contract_id"] = "contract-old"
        self.assertIn(
            "contract_id does not match control state",
            validate_receipt(receipt, self.state),
        )

    def test_rejects_pass_with_blocker(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["finding_or_blocker"] = {"summary": "migration unavailable"}
        self.assertIn(
            "PASS cannot contain a finding or blocker",
            validate_receipt(receipt, self.state),
        )

    def test_rejects_reviewer_mutation(self):
        state = copy.deepcopy(self.state)
        state["lanes"]["lane-api"]["role"] = "integration-reviewer"
        receipt = copy.deepcopy(self.receipt)
        receipt["role"] = "integration-reviewer"
        receipt["output_identity"] = {"artifact_digest": "changed"}
        receipt["input_identity"] = {"artifact_digest": "original"}
        state["lanes"]["lane-api"]["input_identity"] = receipt["input_identity"]
        self.assertIn(
            "reviewer output_identity must equal input_identity",
            validate_receipt(receipt, state),
        )

    def test_rejects_blocked_without_resume_condition(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["status"] = "BLOCKED"
        receipt["finding_or_blocker"] = {
            "attempted_checks": ["checked deploy target"]
        }
        receipt["resume_condition"] = None
        self.assertIn(
            "BLOCKED requires resume_condition",
            validate_receipt(receipt, self.state),
        )


if __name__ == "__main__":
    unittest.main()
