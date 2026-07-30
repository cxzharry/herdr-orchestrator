import unittest

from scripts.herdr_identity import agent_identity, fixed_role_name


class IdentityTest(unittest.TestCase):
    def test_extracts_nested_codex_session_once(self):
        self.assertEqual(
            {
                "name": "p2_impl",
                "pane_id": "w6:p2",
                "workspace_id": "w6",
                "terminal_id": "terminal-2",
                "session_id": "session-2",
                "status": "working",
            },
            agent_identity({
                "name": "p2_impl",
                "pane_id": "w6:p2",
                "workspace_id": "w6",
                "terminal_id": "terminal-2",
                "agent_session": {"value": "session-2"},
                "agent_status": "working",
            }),
        )

    def test_fixed_names_never_include_task_text(self):
        self.assertEqual("p1_orchestrator", fixed_role_name("P1", "w6", set()))
        self.assertEqual("p4_impl", fixed_role_name("P4", "w6", set()))
        self.assertEqual(
            "p4_impl_w6",
            fixed_role_name("P4", "w6", {"p4_impl"}),
        )


if __name__ == "__main__":
    unittest.main()
