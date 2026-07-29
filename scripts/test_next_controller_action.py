import unittest

from scripts.next_controller_action import next_controller_action


class NextControllerActionTests(unittest.TestCase):
    def state(self):
        return {
            "schema_version": "herdr-control-state/v2",
            "contract_id": "contract-b",
            "controller_scope": "scope-b",
            "gate_matrix": {
                "mode": "Standard",
                "applicable": {"P5": True, "P6": True, "P7": True, "P8": True},
            },
            "prerequisites": {
                "implementation_receipts_accepted": True,
                "integration_artifact_ready": False,
                "local_runtime_ready": False,
                "deployment_ready": False,
            },
            "lanes": {
                "impl-a": {"slot": "P2", "state": "ACCEPTED", "generation": 1},
                "impl-b": {"slot": "P3", "state": "ACCEPTED", "generation": 1},
                "integration": {
                    "slot": "P5",
                    "role": "integration-owner",
                    "state": "READY",
                    "generation": 1,
                },
                "review": {
                    "slot": "P6",
                    "role": "integration-reviewer",
                    "state": "READY",
                    "generation": 1,
                },
                "qc": {"slot": "P7", "role": "qc", "state": "READY", "generation": 1},
                "ui": {
                    "slot": "P8",
                    "role": "designer",
                    "state": "READY",
                    "generation": 1,
                },
            },
        }

    def test_ignores_summary_and_other_scope_when_dispatching_integration_gate(self):
        state = self.state()
        state["conversation_summary"] = "continue integration/review"
        state["unrelated_live_agents"] = [
            {"controller_scope": "scope-a", "name": "p1_orchestrator", "slot": "P1"},
            {"controller_scope": "scope-a", "name": "p5_integration_owner", "slot": "P5"},
        ]

        self.assertEqual(
            next_controller_action(state),
            {
                "action": "DISPATCH_GATE",
                "controller_scope": "scope-b",
                "slot": "P5",
                "role": "integration-owner",
            },
        )

    def test_after_artifact_ready_releases_p5_smoke_and_p6_review_in_parallel(self):
        state = self.state()
        state["lanes"]["integration"]["state"] = "ACCEPTED"
        state["prerequisites"]["integration_artifact_ready"] = True

        self.assertEqual(
            next_controller_action(state),
            {
                "action": "DISPATCH_PARALLEL_GATES",
                "controller_scope": "scope-b",
                "gates": [
                    {"slot": "P5", "role": "smoke"},
                    {"slot": "P6", "role": "integration-reviewer"},
                ],
            },
        )

    def test_blocks_p7_p8_until_runtime_or_deployment_prerequisite(self):
        state = self.state()
        state["lanes"]["integration"]["state"] = "ACCEPTED"
        state["lanes"]["review"]["state"] = "ACCEPTED"
        state["prerequisites"]["integration_artifact_ready"] = True

        self.assertEqual(next_controller_action(state)["action"], "BLOCKED_STATE")

    def test_releases_applicable_p7_p8_after_runtime_prerequisite(self):
        state = self.state()
        state["lanes"]["integration"]["state"] = "ACCEPTED"
        state["lanes"]["review"]["state"] = "ACCEPTED"
        state["prerequisites"]["integration_artifact_ready"] = True
        state["prerequisites"]["local_runtime_ready"] = True

        self.assertEqual(
            next_controller_action(state),
            {
                "action": "DISPATCH_PARALLEL_GATES",
                "controller_scope": "scope-b",
                "gates": [
                    {"slot": "P7", "role": "qc"},
                    {"slot": "P8", "role": "designer"},
                ],
            },
        )

    def test_compact_selects_compact_verifier_without_standard_gates(self):
        state = self.state()
        state["gate_matrix"] = {"mode": "Compact", "applicable": {"Compact": True}}

        self.assertEqual(
            next_controller_action(state),
            {
                "action": "DISPATCH_COMPACT_VERIFIER",
                "controller_scope": "scope-b",
            },
        )

    def test_legacy_state_without_gate_matrix_blocks(self):
        state = self.state()
        del state["gate_matrix"]

        self.assertEqual(next_controller_action(state)["action"], "BLOCKED_STATE")


if __name__ == "__main__":
    unittest.main()
