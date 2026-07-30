import tempfile
import unittest
from pathlib import Path

from scripts.controller_router import (
    ControllerRouter,
    RouterError,
    decide_controller_action,
)
from scripts.herdr_identity import ROLE_NAMES
from scripts.workspace_state import create_state, load_state


def agent(name, pane, session, status="done", terminal="term-1", workspace="w1"):
    return {
        "name": name,
        "pane_id": pane,
        "workspace_id": workspace,
        "terminal_id": terminal,
        "agent_status": status,
        "agent_session": {"value": session},
    }


class FakeClient:
    def __init__(self, agents=None):
        self.agents = list(agents or [])
        self.calls = []

    def list_agents(self):
        self.calls.append(("list_agents",))
        return [dict(item) for item in self.agents]

    def rename_agent(self, pane_id, name):
        self.calls.append(("rename_agent", pane_id, name))
        for item in self.agents:
            if item["pane_id"] == pane_id:
                item["name"] = name
                return
        raise RouterError("agent is no longer live")

    def signal_agent(self, name, message):
        self.calls.append(("signal_agent", name, message))


class ControllerDecisionTests(unittest.TestCase):
    def test_ordinary_chat_claims_p1_when_workspace_has_no_controller(self):
        decision = decide_controller_action(
            agent("", "w6:p1", "controller-session", workspace="w6"),
            live_controller=None,
            workspace_id="w6",
        )

        self.assertEqual(decision["action"], "CLAIM_P1")
        self.assertEqual(decision["workspace_id"], "w6")

    def test_existing_controller_continues_after_pane_move_with_stable_session(self):
        current = agent("p1_orchestrator", "w1:p9", "session-a", terminal="term-1")
        live = agent("p1_orchestrator", "w1:p9", "session-a", terminal="term-1")

        decision = decide_controller_action(current, live_controller=live)

        self.assertEqual(decision["action"], "CONTINUE")
        self.assertEqual(decision["session_id"], "session-a")

    def test_worker_chat_forwards_and_never_promotes(self):
        controller = agent(
            "p1_orchestrator", "w6:p1", "controller-session", workspace="w6"
        )
        for slot in ("P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"):
            worker = agent(
                ROLE_NAMES[slot], f"w6:{slot.lower()}", f"{slot.lower()}-session",
                workspace="w6",
            )

            decision = decide_controller_action(
                worker, live_controller=controller, workspace_id="w6"
            )

            self.assertEqual(decision["action"], "FORWARD")
            self.assertEqual(decision["workspace_id"], "w6")

    def test_named_non_controller_blocks_without_existing_controller(self):
        decision = decide_controller_action(
            agent("hdr_p7", "w1:p7", "session-worker"),
            live_controller=None,
        )

        self.assertEqual(decision["action"], "BLOCK")
        self.assertEqual(decision["reason"], "BLOCKED_NO_LOCAL_CONTROLLER")

    def test_named_agent_cannot_take_existing_controller_role(self):
        current = agent("reviewer", "w1:p4", "session-b")
        live = agent("p1_orchestrator", "w1:p1", "session-p1")

        decision = decide_controller_action(current, live_controller=live)

        self.assertEqual(decision["action"], "BLOCK")
        self.assertEqual(decision["reason"], "BLOCKED_ROLE_CONFLICT")


class ControllerRouterTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.state_path = self.root / "workspace-state.json"
        create_state(
            self.state_path,
            "w1",
            controller={"role_name": "p1_orchestrator", "session_id": "session-p1"},
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def router(self, client):
        return ControllerRouter(client=client, state_path=self.state_path, workspace_id="w1")

    def test_promotion_records_fixed_p1_in_workspace_state(self):
        create_state_path = self.root / "empty-workspace-state.json"
        create_state(create_state_path, "w1")
        current = agent("", "w1:p2", "session-a", terminal="term-a")
        client = FakeClient([current])

        router = ControllerRouter(client=client, state_path=create_state_path, workspace_id="w1")
        result = router.claim_p1(current)

        self.assertEqual(result["action"], "CLAIM_P1")
        self.assertEqual(result["controller"]["name"], "p1_orchestrator")
        self.assertEqual(load_state(create_state_path)["controller"]["session_id"], "session-a")
        self.assertEqual(client.calls, [("rename_agent", "w1:p2", "p1_orchestrator")])

    def test_worker_request_persists_envelope_to_workspace_inbox_then_signals(self):
        current = agent("p3_impl", "w1:p3", "session-worker", terminal="term-w")
        controller = agent("p1_orchestrator", "w1:p1", "session-p1", status="idle")
        client = FakeClient([controller, current])
        request = {"summary": "inspect docs", "affected_paths": ["docs/**"]}

        first = self.router(client).forward_request(current, controller, request)
        second = self.router(client).forward_request(current, controller, request)

        self.assertEqual(first["action"], "FORWARD")
        self.assertEqual(first["request_id"], second["request_id"])
        inbox = load_state(self.state_path)["inbox"]
        self.assertEqual(1, len(inbox))
        self.assertEqual(inbox[0]["request"], request)
        self.assertEqual(inbox[0]["from"]["session_id"], "session-worker")
        signals = [call for call in client.calls if call[0] == "signal_agent"]
        self.assertEqual(signals, [("signal_agent", "p1_orchestrator", first["request_id"])])

    def test_busy_controller_queues_without_signal(self):
        current = agent("p4_impl", "w1:p4", "session-worker", terminal="term-w")
        controller = agent("p1_orchestrator", "w1:p1", "session-p1", status="working")
        client = FakeClient([controller, current])

        result = self.router(client).forward_request(
            current, controller, {"summary": "second delta"}
        )

        self.assertEqual(result["action"], "FORWARD")
        self.assertFalse(any(call[0] == "signal_agent" for call in client.calls))
        self.assertEqual(1, len(load_state(self.state_path)["inbox"]))

    def test_request_id_ignores_controller_and_worker_location_moves(self):
        request = {"summary": "same user delta", "affected_paths": ["scripts/**"]}
        first_worker = agent("p4_impl", "w1:p4", "session-worker", terminal="term-w")
        first_controller = agent("p1_orchestrator", "w1:p1", "session-p1", terminal="term-p1")
        moved_worker = agent(
            "p4_impl", "w1:p8", "session-worker", terminal="term-w-moved"
        )
        moved_controller = agent(
            "p1_orchestrator", "w1:p9", "session-p1", terminal="term-p1-moved"
        )

        first = self.router(FakeClient([])).forward_request(first_worker, first_controller, request)
        moved = self.router(FakeClient([])).forward_request(moved_worker, moved_controller, request)

        self.assertEqual(first["request_id"], moved["request_id"])


if __name__ == "__main__":
    unittest.main()
