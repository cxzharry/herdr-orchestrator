import unittest

from scripts.render_agent_status import render_agent_status
from scripts.workspace_state import initial_state


class RenderAgentStatusTests(unittest.TestCase):
    def test_status_separates_fixed_role_from_current_task(self):
        state = initial_state("w6")
        state["slots"]["P2"]["status"] = "BUSY"
        state["slots"]["P2"]["task_summary"] = "unify workspace ledger"

        self.assertEqual(
            "P2 | p2_impl | BUSY | unify workspace ledger",
            render_agent_status(state)[1],
        )


if __name__ == "__main__":
    unittest.main()
