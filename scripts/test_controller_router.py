import json
import threading
import tempfile
import unittest
from pathlib import Path

from scripts.controller_router import (
    ControllerRouter,
    RouterError,
    controller_scope_id,
    decide_controller_action,
)


def agent(name, pane, session, status="done", terminal="term-1"):
    return {
        "name": name,
        "pane_id": pane,
        "workspace_id": pane.split(":")[0],
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

    def test_worker_in_another_workspace_never_forwards_to_controller(self):
        current = agent("hdr_p2", "w6:p2", "session-worker")
        live = agent("hdr_p1", "w5:p1", "session-p1")

        decision = decide_controller_action(current, live_controller=live)

        self.assertEqual(decision["action"], "BLOCK")
        self.assertEqual(decision["reason"], "BLOCKED_WORKSPACE_MISMATCH")

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


class DynamicControllerDecisionTests(unittest.TestCase):
    def test_unnamed_main_chat_with_distinct_session_promotes_despite_existing_scoped_p1(self):
        current = agent("", "w1:p8", "session-new")
        controller = agent("p1_orchestrator", "w1:p1", "session-p1")

        result = decide_controller_action(current, controller)

        self.assertEqual(result["action"], "PROMOTE")
        self.assertEqual(result["session_id"], "session-new")

    def test_unnamed_main_chat_in_another_workspace_does_not_promote_to_scoped_p1(self):
        current = agent("", "w6:p8", "session-new")
        controller = agent("p1_orchestrator", "w1:p1", "session-p1")

        result = decide_controller_action(current, controller)

        self.assertEqual(result["action"], "BLOCK")
        self.assertEqual(result["reason"], "BLOCKED_WORKSPACE_MISMATCH")

    def test_dynamic_worker_forwards_to_dynamic_controller(self):
        current = agent("p2_impl_auth", "w1:p2", "session-worker")
        controller = agent(
            "p1_orchestrator",
            "w1:p1",
            "session-p1",
            status="idle",
        )

        result = decide_controller_action(current, controller)

        self.assertEqual(result["action"], "FORWARD")
        self.assertEqual(result["controller_pane_id"], "w1:p1")

    def test_legacy_worker_still_forwards_during_migration(self):
        current = agent("hdr_p7", "w1:p7", "session-worker")
        controller = agent("p1_orchestrator", "w1:p1", "session-p1")

        result = decide_controller_action(current, controller)

        self.assertEqual(result["action"], "FORWARD")


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
        self.assertEqual(result["controller"]["name"], "p1_orchestrator")
        self.assertEqual(result["controller"]["pane_id"], "w1:p2")
        self.assertEqual(result["controller"]["session_id"], "session-a")
        self.assertEqual(
            client.calls,
            [
                ("list_agents",),
                ("rename_agent", "w1:p2", "p1_orchestrator"),
                ("list_agents",),
            ],
        )

    def test_promotion_renames_controller_to_visible_role(self):
        current = agent("", "w1:p2", "session-new", terminal="term-new")
        client = FakeClient(
            [agent("", "w1:p2", "session-new", terminal="term-new")]
        )
        router = ControllerRouter(client, self.root, "sock-a")

        result = router.promote(current)

        self.assertEqual(result["controller"]["name"], "p1_orchestrator")
        self.assertIn(
            ("rename_agent", "w1:p2", "p1_orchestrator"),
            client.calls,
        )

    def test_first_tick_migrates_legacy_controller_without_new_session(self):
        current = agent(
            "hdr_p1",
            "w1:p7",
            "session-p1",
            terminal="term-p1",
            status="working",
        )
        client = FakeClient([current])
        router = ControllerRouter(client, self.root, "sock-a")

        result = router.ensure_controller_name(current)

        self.assertEqual(result["name"], "p1_orchestrator")
        self.assertEqual(result["session_id"], "session-p1")
        self.assertIn(
            ("rename_agent", "w1:p7", "p1_orchestrator"),
            client.calls,
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
        scope = controller_scope_id("session-p1")
        request_path = self.root / "sock-a" / scope / "p1-inbox" / f"{first['request_id']}.json"
        stored = json.loads(request_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["request"], request)
        self.assertEqual(stored["from"]["session_id"], "session-worker")
        self.assertEqual(stored["controller"]["session_id"], "session-p1")
        signals = [call for call in client.calls if call[0] == "signal_agent"]
        self.assertEqual(signals, [("signal_agent", "hdr_p1", first["request_id"])])

    def test_worker_request_rejects_cross_workspace_controller(self):
        current = agent("hdr_p3", "w6:p3", "session-worker", terminal="term-w")
        controller = agent("hdr_p1", "w5:p1", "session-p1", status="idle")
        client = FakeClient([controller, current])
        router = ControllerRouter(client=client, inbox_root=self.root, socket_key="sock-a")

        with self.assertRaisesRegex(RouterError, "workspace mismatch"):
            router.forward_request(current, controller, {"text": "wrong space"})

        self.assertFalse(any(call[0] == "signal_agent" for call in client.calls))

    def test_busy_controller_queues_without_signal(self):
        current = agent("hdr_p4", "w1:p4", "session-worker", terminal="term-w")
        controller = agent("hdr_p1", "w1:p1", "session-p1", status="working")
        client = FakeClient([controller, current])
        router = ControllerRouter(client=client, inbox_root=self.root, socket_key="sock-a")

        result = router.forward_request(current, controller, {"text": "second delta"})

        self.assertEqual(result["action"], "QUEUED")
        self.assertFalse(any(call[0] == "signal_agent" for call in client.calls))

    def test_request_id_ignores_volatile_runtime_status(self):
        request = {"text": "same user delta"}
        ids = []
        for status in ("idle", "working", "blocked"):
            current = agent("hdr_p4", "w1:p4", "session-worker", status=status)
            controller = agent("hdr_p1", "w1:p1", "session-p1", status=status)
            router = ControllerRouter(
                client=FakeClient([controller, current]),
                inbox_root=self.root / status,
                socket_key="sock-a",
            )

            ids.append(
                router.forward_request(current, controller, request)["request_id"]
            )

        self.assertEqual(ids, [ids[0], ids[0], ids[0]])

    def test_request_id_changes_for_different_request_or_source_identity(self):
        controller = agent("hdr_p1", "w1:p1", "session-p1", status="idle")
        current = agent("hdr_p4", "w1:p4", "session-worker")
        router = ControllerRouter(
            client=FakeClient([controller, current]),
            inbox_root=self.root,
            socket_key="sock-a",
        )

        first = router.forward_request(current, controller, {"text": "delta-a"})
        different_request = router.forward_request(current, controller, {"text": "delta-b"})
        different_source = router.forward_request(
            agent("hdr_p4", "w1:p4", "session-other"),
            controller,
            {"text": "delta-a"},
        )

        self.assertNotEqual(first["request_id"], different_request["request_id"])
        self.assertNotEqual(first["request_id"], different_source["request_id"])

    def test_request_id_ignores_controller_and_worker_location_moves(self):
        request = {"text": "same user delta", "paths": ["scripts/controller_router.py"]}
        first_router = ControllerRouter(
            client=FakeClient([]),
            inbox_root=self.root / "first",
            socket_key="sock-a",
        )
        moved_router = ControllerRouter(
            client=FakeClient([]),
            inbox_root=self.root / "moved",
            socket_key="sock-a",
        )
        first_worker = agent("hdr_p4", "w1:p4", "session-worker", terminal="term-w")
        first_controller = agent("hdr_p1", "w1:p1", "session-p1", terminal="term-p1")
        moved_worker = {
            **agent("hdr_p4", "w2:p8", "session-worker", terminal="term-w-moved"),
            "workspace_id": "w2",
        }
        moved_controller = {
            **agent("hdr_p1", "w2:p1", "session-p1", terminal="term-p1-moved"),
            "workspace_id": "w2",
        }

        first = first_router.forward_request(first_worker, first_controller, request)
        moved = moved_router.forward_request(moved_worker, moved_controller, request)

        self.assertEqual(first["request_id"], moved["request_id"])

    def test_request_id_survives_role_and_task_rename(self):
        controller = agent(
            "p1_orchestrator",
            "w1:p1",
            "session-p1",
            status="idle",
        )
        router = ControllerRouter(
            client=FakeClient([controller]),
            inbox_root=self.root,
            socket_key="sock-a",
        )
        request = {"text": "same user delta"}

        first = router.forward_request(
            agent("p2_impl_auth", "w1:p2", "session-worker"),
            controller,
            request,
        )
        renamed = router.forward_request(
            agent("p2_impl_schema", "w1:p8", "session-worker"),
            controller,
            request,
        )

        self.assertEqual(first["request_id"], renamed["request_id"])

    def test_concurrent_promotions_get_separate_controller_scopes(self):
        agents = [
            agent("", "w1:p2", "session-a", terminal="term-a"),
            agent("", "w2:p2", "session-b", terminal="term-b"),
        ]
        client = FakeClient(agents)
        router = ControllerRouter(client, self.root, "sock-a")
        barrier = threading.Barrier(2)
        results = []

        def promote(current):
            barrier.wait(timeout=2)
            results.append(router.promote(current))

        threads = [threading.Thread(target=promote, args=(item,)) for item in agents]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)

        controllers = [result["controller"] for result in results]
        scopes = {controller["controller_scope"] for controller in controllers}
        names = {controller["name"] for controller in controllers}
        self.assertEqual(len(scopes), 2)
        self.assertEqual(len(names), 2)
        self.assertTrue(all(name.startswith("p1_orchestrator") for name in names))
        self.assertTrue(
            all((self.root / "sock-a" / scope / "p1-inbox").is_dir() for scope in scopes)
        )
        registry = json.loads(
            (self.root / "sock-a" / "runtime-registry.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(registry["controller_scopes"]), scopes)

        controller_a = next(item for item in controllers if item["session_id"] == "session-a")
        controller_b = next(item for item in controllers if item["session_id"] == "session-b")
        request = router.forward_request(
            agent("p2_impl_auth", "w1:p5", "worker-a"),
            controller_a,
            {"text": "scope-a only"},
        )

        self.assertTrue(
            (self.root / "sock-a" / controller_a["controller_scope"] / "p1-inbox" / f"{request['request_id']}.json").is_file()
        )
        self.assertFalse(
            (self.root / "sock-a" / controller_b["controller_scope"] / "p1-inbox" / f"{request['request_id']}.json").exists()
        )
        self.assertNotIn(("rename_agent", controller_b["pane_id"], controller_a["name"]), client.calls)

    def test_legacy_inbox_migrates_once_to_claiming_controller_scope(self):
        legacy = self.root / "sock-a" / "p1-inbox"
        legacy.mkdir(parents=True)
        first = legacy / "req-a.json"
        second = legacy / "req-b.json"
        first.write_text('{"request_id":"req-a","text":"a"}\n', encoding="utf-8")
        second.write_text('{"request_id":"req-b","text":"b"}\n', encoding="utf-8")
        controller = agent("hdr_p1", "w1:p1", "session-p1")
        other = agent("", "w2:p1", "session-other")
        router = ControllerRouter(FakeClient([controller, other]), self.root, "sock-a")

        migrated = router.ensure_controller_name(controller)
        other_controller = router.promote(other)["controller"]
        resumed = router.ensure_controller_name(migrated)

        scoped = self.root / "sock-a" / migrated["controller_scope"] / "p1-inbox"
        other_scoped = self.root / "sock-a" / other_controller["controller_scope"] / "p1-inbox"
        self.assertFalse(first.exists())
        self.assertEqual((scoped / "req-a.json").read_text(encoding="utf-8"), '{"request_id":"req-a","text":"a"}\n')
        self.assertEqual((scoped / "req-b.json").read_text(encoding="utf-8"), '{"request_id":"req-b","text":"b"}\n')
        self.assertTrue((scoped / ".legacy-migrated").is_file())
        self.assertFalse((other_scoped / "req-a.json").exists())
        self.assertEqual(resumed["controller_scope"], migrated["controller_scope"])


if __name__ == "__main__":
    unittest.main()
