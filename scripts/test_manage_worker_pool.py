import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from scripts.manage_worker_pool import JsonState, PoolError, WorkerPool, default_state_path


def live_agent(
    name: str,
    pane: str,
    session: str,
    status: str = "done",
) -> dict:
    return {
        "name": name,
        "pane_id": pane,
        "workspace_id": "w6",
        "terminal_id": f"term-{pane}",
        "agent_status": status,
        "agent_session": {"value": session},
    }


class FakeClient:
    def __init__(
        self,
        agents=None,
        sessions_on_start=True,
        sessions_on_reset=True,
        sessions_on_list_after=None,
        invalid_argv_once=False,
    ):
        self.agents = list(agents or [])
        self.calls = []
        self.sessions_on_start = sessions_on_start
        self.sessions_on_reset = sessions_on_reset
        self.sessions_on_list_after = sessions_on_list_after
        self.invalid_argv_once = invalid_argv_once
        self.list_count = 0

    def list_agents(self):
        self.calls.append(("list",))
        self.list_count += 1
        if (
            self.sessions_on_list_after is not None
            and self.list_count >= self.sessions_on_list_after
        ):
            for index, agent in enumerate(self.agents):
                agent.setdefault(
                    "agent_session",
                    {"value": f"first-session-{index}"},
                )
        return list(self.agents)

    def create_panes(self, count, cwd):
        self.calls.append(("create_panes", count, cwd))
        first = len(self.agents) + 3
        return [f"w6:p{index + first}" for index in range(count)]

    def start_workers(self, workers):
        self.calls.append(("start_workers", workers))
        started = []
        for worker in workers:
            agent = live_agent(
                worker["name"],
                worker["pane_id"],
                f"session-{worker['slot'].lower()}",
            )
            if not self.sessions_on_start:
                agent.pop("agent_session")
            self.agents.append(agent)
            started.append(
                {
                    "agent": agent,
                    "argv": [
                        "codex",
                        "--yolo",
                        "--model",
                        "gpt-5.5",
                        "-c",
                        'model_reasoning_effort="medium"',
                    ],
                }
            )
        if self.invalid_argv_once:
            self.invalid_argv_once = False
            started[0]["argv"] = ["codex", "--model", "wrong"]
        return started

    def ensure_ready(self, workers, previous_sessions=None):
        self.calls.append(("ensure_ready", workers, previous_sessions or {}))
        previous_sessions = previous_sessions or {}
        ready = []
        for worker in workers:
            agent = next(agent for agent in self.agents if agent["name"] == worker["name"])
            if "agent_session" not in agent and self.sessions_on_start:
                agent["agent_session"] = {"value": f"ready-{worker['slot'].lower()}"}
            elif (
                "agent_session" in agent
                and previous_sessions.get(worker["name"]) == agent["agent_session"]["value"]
                and self.sessions_on_reset
            ):
                agent["agent_session"]["value"] += "-new"
            ready.append(agent)
        return ready

    def reset(self, name):
        self.calls.append(("reset", name))

    def quarantine(self, name):
        self.calls.append(("quarantine", name))
        agent = next(agent for agent in self.agents if agent["name"] == name)
        agent["name"] = f"orphan_{name}"


class WorkerPoolTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tempdir.name) / "pool.json"

    def tearDown(self):
        self.tempdir.cleanup()

    def pool(self, client):
        return WorkerPool(
            client=client,
            state_path=self.state_path,
            workspace_id="w6",
            anchor_pane_id="w6:p1",
        )

    def test_first_prepare_creates_three_yolo_medium_workers(self):
        client = FakeClient()

        result = self.pool(client).prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(result["action"], "created")
        self.assertEqual([worker["slot"] for worker in result["workers"]], ["P2", "P3", "P4"])
        starts = next(call[1] for call in client.calls if call[0] == "start_workers")
        self.assertEqual(len(starts), 3)
        self.assertTrue(all(worker["name"].startswith("hdr_") for worker in starts))
        self.assertTrue(all(worker["pane_id"].startswith("w6:p") for worker in starts))

    def test_first_prepare_clears_startup_gate_before_first_session_binds(self):
        client = FakeClient(sessions_on_start=False)
        pool = self.pool(client)

        result = pool.prepare("contract-a", "/tmp/project", 3)

        self.assertTrue(all(worker["input_ready"] for worker in result["workers"]))
        self.assertTrue(all(worker["session_id"] is None for worker in result["workers"]))
        self.assertTrue(all(worker["rebind_pending"] for worker in result["workers"]))
        self.assertEqual(
            len([call for call in client.calls if call[0] == "ensure_ready"]),
            1,
        )
        for index, agent in enumerate(client.agents):
            agent["agent_session"] = {"value": f"first-session-{index}"}

        bound = pool.bind("contract-a")
        self.assertTrue(all(not worker["rebind_pending"] for worker in bound["workers"]))

    def test_same_contract_reuses_without_mutating_commands(self):
        client = FakeClient()
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project", 3)
        client.calls.clear()

        result = pool.prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(result["action"], "reused")
        self.assertEqual(client.calls, [("list",)])

    def test_new_contract_can_return_input_ready_before_session_rebind(self):
        client = FakeClient(sessions_on_reset=False)
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project-a", 3)
        client.calls.clear()

        result = pool.prepare("contract-b", "/tmp/project-b", 3)

        self.assertEqual(result["action"], "reset")
        self.assertEqual(
            [call for call in client.calls if call[0] == "reset"],
            [("reset", "hdr_p2"), ("reset", "hdr_p3"), ("reset", "hdr_p4")],
        )
        self.assertTrue(all(worker["input_ready"] for worker in result["workers"]))
        self.assertTrue(all(worker["rebind_pending"] for worker in result["workers"]))

    def test_prepare_refuses_to_hijack_busy_worker_for_another_contract(self):
        client = FakeClient()
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project", 3)
        client.agents[1]["agent_status"] = "working"

        with self.assertRaisesRegex(PoolError, "hdr_p3.*working"):
            pool.prepare("contract-b", "/tmp/project", 3)

        self.assertFalse(any(call[0] == "reset" for call in client.calls))

    def test_same_contract_controller_attaches_to_busy_workers(self):
        client = FakeClient()
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project", 3)
        client.agents[1]["agent_status"] = "working"
        client.calls.clear()

        result = WorkerPool(
            client=client,
            state_path=self.state_path,
            workspace_id="w8",
            anchor_pane_id="w8:p1",
        ).prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(result["status"], "busy")
        self.assertEqual(result["action"], "attached")
        self.assertEqual(client.calls, [("list",)])

    def test_bind_requires_new_session_after_cross_contract_reset(self):
        client = FakeClient(sessions_on_reset=False)
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project-a", 3)
        pool.prepare("contract-b", "/tmp/project-b", 3)
        for agent in client.agents:
            agent["agent_session"]["value"] += "-new"

        result = pool.bind("contract-b")

        self.assertEqual(result["action"], "bound")
        self.assertTrue(all(not worker["rebind_pending"] for worker in result["workers"]))
        self.assertTrue(all(worker["session_id"].endswith("-new") for worker in result["workers"]))

    def test_bind_rejects_wrong_contract(self):
        client = FakeClient()
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project", 3)

        with self.assertRaisesRegex(PoolError, "contract mismatch"):
            pool.bind("contract-b")

    def test_same_pool_is_reused_by_controller_in_another_workspace(self):
        client = FakeClient()
        self.pool(client).prepare("contract-a", "/tmp/project", 3)
        client.calls.clear()
        moved_controller = WorkerPool(
            client=client,
            state_path=self.state_path,
            workspace_id="w8",
            anchor_pane_id="w8:p1",
        )

        result = moved_controller.prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(result["action"], "reused")
        self.assertEqual(client.calls, [("list",)])

    def test_unique_legacy_workspace_ledger_is_adopted_as_active_pool(self):
        client = FakeClient()
        legacy_path = Path(self.tempdir.name) / "w5.json"
        WorkerPool(
            client=client,
            state_path=legacy_path,
            workspace_id="w5",
            anchor_pane_id="w5:p1",
        ).prepare("contract-a", "/tmp/project", 3)
        active_path = Path(self.tempdir.name) / "active.json"
        client.calls.clear()

        result = WorkerPool(
            client=client,
            state_path=active_path,
            workspace_id="w8",
            anchor_pane_id="w8:p1",
        ).prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(result["action"], "reused")
        self.assertTrue(active_path.is_file())
        self.assertFalse(legacy_path.exists())
        self.assertEqual(client.calls, [("list",)])

    def test_default_pool_ledger_is_not_workspace_scoped(self):
        with patch.dict(os.environ, {"HERDR_SOCKET_PATH": "/tmp/herdr-a.sock"}):
            first = default_state_path("w6")
            moved = default_state_path("w8")
        with patch.dict(os.environ, {"HERDR_SOCKET_PATH": "/tmp/herdr-b.sock"}):
            another_session = default_state_path("w6")

        self.assertTrue(first.name.startswith("active-"))
        self.assertEqual(moved, first)
        self.assertNotEqual(another_session, first)

    def test_pool_rejects_a_ledger_from_another_herdr_session(self):
        client = FakeClient()
        with patch.dict(os.environ, {"HERDR_SOCKET_PATH": "/tmp/herdr-a.sock"}):
            self.pool(client).prepare("contract-a", "/tmp/project", 3)
        with patch.dict(os.environ, {"HERDR_SOCKET_PATH": "/tmp/herdr-b.sock"}):
            other_session = self.pool(client)

        with self.assertRaisesRegex(PoolError, "Herdr session mismatch"):
            other_session.prepare("contract-a", "/tmp/project", 3)

    def test_prepare_rebinds_a_worker_moved_with_the_same_session(self):
        client = FakeClient()
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project", 3)
        client.agents[1]["pane_id"] = "w8:p9"
        client.agents[1]["workspace_id"] = "w8"
        client.calls.clear()

        result = pool.prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(result["action"], "rebound")
        worker = next(worker for worker in result["workers"] if worker["name"] == "hdr_p3")
        self.assertEqual(worker["pane_id"], "w8:p9")
        self.assertEqual(worker["workspace_id"], "w8")
        self.assertFalse(any(call[0] == "start_workers" for call in client.calls))

    def test_prepare_recreates_only_a_closed_worker(self):
        client = FakeClient()
        pool = self.pool(client)
        original = pool.prepare("contract-a", "/tmp/project", 3)
        original_sessions = {
            worker["name"]: worker["session_id"] for worker in original["workers"]
        }
        client.agents = [
            agent for agent in client.agents if agent["name"] != "hdr_p3"
        ]
        client.calls.clear()

        result = pool.prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(result["action"], "recovered")
        starts = next(call[1] for call in client.calls if call[0] == "start_workers")
        self.assertEqual([worker["name"] for worker in starts], ["hdr_p3"])
        sessions = {
            worker["name"]: worker["session_id"] for worker in result["workers"]
        }
        self.assertEqual(sessions["hdr_p2"], original_sessions["hdr_p2"])
        self.assertEqual(sessions["hdr_p4"], original_sessions["hdr_p4"])

    def test_prepare_expands_an_existing_pool_to_requested_count(self):
        client = FakeClient()
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project", 1)
        client.calls.clear()

        result = pool.prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(result["action"], "recovered")
        self.assertEqual(
            [worker["slot"] for worker in result["workers"]],
            ["P2", "P3", "P4"],
        )
        starts = next(call[1] for call in client.calls if call[0] == "start_workers")
        self.assertEqual(
            [worker["name"] for worker in starts],
            ["hdr_p3", "hdr_p4"],
        )

    def test_wrong_root_is_rejected_before_recovering_a_closed_worker(self):
        client = FakeClient()
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project", 3)
        client.agents = [
            agent for agent in client.agents if agent["name"] != "hdr_p3"
        ]
        client.calls.clear()

        with self.assertRaisesRegex(PoolError, "same contract cannot change root"):
            pool.prepare("contract-a", "/tmp/other-project", 3)

        self.assertFalse(any(call[0] == "create_panes" for call in client.calls))
        self.assertFalse(any(call[0] == "start_workers" for call in client.calls))

    def test_bind_is_non_fatal_until_first_prompt_creates_sessions(self):
        client = FakeClient(sessions_on_start=False)
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project", 3)

        pending = pool.bind("contract-a")

        self.assertEqual(pending["action"], "pending")
        self.assertTrue(all(worker["rebind_pending"] for worker in pending["workers"]))
        for index, agent in enumerate(client.agents):
            agent["agent_session"] = {"value": f"first-session-{index}"}

        bound = pool.bind("contract-a")
        self.assertEqual(bound["action"], "bound")
        self.assertTrue(all(not worker["rebind_pending"] for worker in bound["workers"]))

    def test_bind_waits_briefly_for_first_prompt_sessions(self):
        client = FakeClient(
            sessions_on_start=False,
            sessions_on_list_after=3,
        )
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project", 3)

        bound = pool.bind("contract-a", wait_seconds=0.2)

        self.assertEqual(bound["action"], "bound")
        self.assertGreaterEqual(client.list_count, 3)

    def test_pending_bind_rejects_replaced_terminal_identity(self):
        client = FakeClient(sessions_on_start=False)
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project", 3)
        client.agents[1]["terminal_id"] = "unrelated-terminal"
        client.agents[1]["agent_session"] = {"value": "unrelated-session"}

        with self.assertRaisesRegex(PoolError, "terminal identity mismatch"):
            pool.bind("contract-a")

    def test_state_save_rejects_a_stale_writer(self):
        state_a = JsonState(self.state_path)
        state_b = JsonState(self.state_path)
        initial = {"revision": 1}
        state_a.load()
        state_a.save(initial)
        state_a.load()
        state_b.load()
        state_a.save({"revision": 2})

        with self.assertRaisesRegex(PoolError, "changed concurrently"):
            state_b.save({"revision": 3})

    def test_prepare_holds_the_state_lock_for_the_complete_transaction(self):
        entered = []

        @contextmanager
        def tracking_lock(_state):
            entered.append("enter")
            yield
            entered.append("exit")

        client = FakeClient()
        with patch.object(JsonState, "locked", tracking_lock, create=True):
            self.pool(client).prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(entered, ["enter", "exit"])
        self.assertEqual(client.calls[0], ("list",))

    def test_failed_closed_worker_recovery_is_quarantined_and_resumable(self):
        client = FakeClient()
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project", 3)
        client.agents = [
            agent for agent in client.agents if agent["name"] != "hdr_p3"
        ]
        client.invalid_argv_once = True

        with self.assertRaisesRegex(PoolError, "worker launch invariant failed"):
            pool.prepare("contract-a", "/tmp/project", 3)

        self.assertTrue(any(call[0] == "quarantine" for call in client.calls))
        recovered = pool.prepare("contract-a", "/tmp/project", 3)
        self.assertEqual(recovered["action"], "recovered")
        self.assertTrue(any(agent["name"] == "hdr_p3" for agent in client.agents))


if __name__ == "__main__":
    unittest.main()
