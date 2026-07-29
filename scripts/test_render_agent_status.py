import unittest

from scripts.render_agent_status import render_agent_status


class RenderAgentStatusTests(unittest.TestCase):
    def test_renders_ordered_p1_to_p9_dynamic_status(self):
        agents = [
            {"name": "unknown", "agent_status": "working"},
            {"name": "p7_qc_rbac", "agent_status": "working"},
            {"name": "p1_orchestrator_a1b2", "agent_status": "working"},
            {"name": "p2_impl_auth", "agent_status": "working"},
            {"name": "p9_persona_admin", "agent_status": "idle"},
            {"name": "p4_worker_ready", "agent_status": "idle"},
            {"name": "p6_integration_review", "agent_status": "done"},
            {"name": "p8_ui_review", "agent_status": "done"},
            {"name": "p3_impl_schema", "agent_status": "done"},
            {"name": "p5_integration_owner", "agent_status": "idle"},
            {"name": "p1_orchestrator", "agent_status": "idle"},
        ]

        self.assertEqual(
            render_agent_status(agents),
            "\n".join(
                [
                    "P1 p1_orchestrator idle",
                    "P1 p1_orchestrator_a1b2 working",
                    "P2 p2_impl_auth working",
                    "P3 p3_impl_schema done",
                    "P4 p4_worker_ready idle",
                    "P5 p5_integration_owner idle",
                    "P6 p6_integration_review done",
                    "P7 p7_qc_rbac working",
                    "P8 p8_ui_review done",
                    "P9 p9_persona_admin idle",
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
