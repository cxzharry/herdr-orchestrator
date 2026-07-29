import json
import tempfile
import unittest
from pathlib import Path

from scripts.controller_router import (
    ControllerRouter,
    RouterError,
    decide_controller_action,
)


def agent(name, pane, session, status="done", terminal="term-1"):
    return {
        "name": name,
        "pane_id": pane,
        "workspace_id": "w1",
        "terminal_id": terminal,
        "agent_status": status,
        "agent_session": {"value": session},
    }


class FakeClient:
    def __init__(self, agents):
        self.agents = list(agents)
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
    def test_eligible_unnamed_agent_promotes_when_no_controller_exists(self):
        current = agent("", "w1:p2", "session-a")

        decision = decide_controller_action(current, live_controller=None)

        self.assertEqual(decision["action"], "PROMOTE")

    def test_existing_controller_continues_after_pane_move_with_stable_session(self):
        current = agent("hdr_p1", "w1:p9", "session-a", terminal="term-1")
        live = agent("hdr_p1", "w1:p9", "session-a", terminal="term-1")

        decision = decide_controller_action(current, live_controller=live)

        self.assertEqual(decision["action"], "CONTINUE")
        self.assertEqual(decision["session_id"], "session-a")

    def test_worker_never_promotes_and_forwards_to_live_controller(self):
        current = agent("hdr_p2", "w1:p2", "session-worker")
        live = agent("hdr_p1", "w1:p1", "session-p1")

        decision = decide_controller_action(current, live_controller=live)

        self.assertEqual(decision["action"], "FORWARD")
        self.assertEqual(decision["controller_session_id"], "session-p1")

    def test_named_non_controller_blocks_without_existing_controller(self):
        current = agent("hdr_p7", "w1:p7", "session-worker")

        decision = decide_controller_action(current, live_controller=None)

        self.assertEqual(decision["action"], "BLOCK")
        self.assertEqual(decision["reason"], "BLOCKED_NO_CONTROLLER")

    def test_named_agent_cannot_take_existing_controller_role(self):
        current = agent("reviewer", "w1:p4", "session-b")
        live = agent("hdr_p1", "w1:p1", "session-p1")

        decision = decide_controller_action(current, live_controller=live)

        self.assertEqual(decision["action"], "BLOCK")
        self.assertEqual(decision["reason"], "BLOCKED_ROLE_CONFLICT")


class ControllerRouterTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_promotion_rechecks_pane_terminal_and_stable_session_identity(self):
        current = agent("", "w1:p2", "session-a", terminal="term-a")
        client = FakeClient([current])
        router = ControllerRouter(client=client, inbox_root=self.root, socket_key="sock-a")

        result = router.promote(current)

        self.assertEqual(result["action"], "PROMOTE")
        self.assertEqual(result["controller"]["name"], "hdr_p1")
        self.assertEqual(result["controller"]["pane_id"], "w1:p2")
        self.assertEqual(result["controller"]["session_id"], "session-a")
        self.assertEqual(
            client.calls,
            [
                ("rename_agent", "w1:p2", "hdr_p1"),
                ("list_agents",),
            ],
        )

    def test_promotion_fails_closed_when_session_changes_during_recheck(self):
        current = agent("", "w1:p2", "session-a", terminal="term-a")
        changed = agent("", "w1:p2", "session-b", terminal="term-a")
        client = FakeClient([changed])
        router = ControllerRouter(client=client, inbox_root=self.root, socket_key="sock-a")

        with self.assertRaisesRegex(RouterError, "session identity changed"):
            router.promote(current)

    def test_worker_request_persists_exact_envelope_and_signals_only_request_id(self):
        current = agent("hdr_p3", "w1:p3", "session-worker", terminal="term-w")
        controller = agent("hdr_p1", "w1:p1", "session-p1", status="idle")
        client = FakeClient([controller, current])
        router = ControllerRouter(client=client, inbox_root=self.root, socket_key="sock-a")
        request = {"text": "please inspect docs", "nested": {"keep": [1, 2]}}

        first = router.forward_request(current, controller, request)
        second = router.forward_request(current, controller, request)

        self.assertEqual(first["action"], "FORWARDED")
        self.assertEqual(first["request_id"], second["request_id"])
        request_path = self.root / "sock-a" / "p1-inbox" / f"{first['request_id']}.json"
        stored = json.loads(request_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["request"], request)
        self.assertEqual(stored["from"]["session_id"], "session-worker")
        self.assertEqual(stored["controller"]["session_id"], "session-p1")
        signals = [call for call in client.calls if call[0] == "signal_agent"]
        self.assertEqual(signals, [("signal_agent", "hdr_p1", first["request_id"])])

    def test_busy_controller_queues_without_signal(self):
        current = agent("hdr_p4", "w1:p4", "session-worker", terminal="term-w")
        controller = agent("hdr_p1", "w1:p1", "session-p1", status="working")
        client = FakeClient([controller, current])
        router = ControllerRouter(client=client, inbox_root=self.root, socket_key="sock-a")

        result = router.forward_request(current, controller, {"text": "second delta"})

        self.assertEqual(result["action"], "QUEUED")
        self.assertFalse(any(call[0] == "signal_agent" for call in client.calls))


if __name__ == "__main__":
    unittest.main()
