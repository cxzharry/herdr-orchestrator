import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from scripts.manage_worker_pool import (
    HerdrClient,
    JsonState,
    PoolError,
    WorkerPool,
    default_state_path,
)


def live_agent(
    name: str,
    pane: str,
    session: str,
    status: str = "done",
    workspace_id: str | None = None,
) -> dict:
    return {
        "name": name,
        "pane_id": pane,
        "workspace_id": workspace_id or pane.split(":")[0],
        "terminal_id": f"term-{pane}",
        "agent_status": status,
        "agent_session": {"value": session},
    }


def json_state(value: dict) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


class FakeClient:
    def __init__(
        self,
        agents=None,
        sessions_on_start=True,
        sessions_on_reset=True,
        sessions_on_list_after=None,
        invalid_argv_once=False,
        workspace_id="w6",
    ):
        self.agents = list(agents or [])
        self.calls = []
        self.sessions_on_start = sessions_on_start
        self.sessions_on_reset = sessions_on_reset
        self.sessions_on_list_after = sessions_on_list_after
        self.invalid_argv_once = invalid_argv_once
        self.workspace_id = workspace_id
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
        return [f"{self.workspace_id}:p{index + first}" for index in range(count)]

    def start_workers(self, workers):
        self.calls.append(("start_workers", workers))
        started = []
        for worker in workers:
            agent = live_agent(
                worker["name"],
                worker["pane_id"],
                f"session-{worker['name']}",
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

    def rename_agent(self, target, name):
        self.calls.append(("rename_agent", target, name))
        agent = next(
            agent
            for agent in self.agents
            if agent["name"] == target or agent["pane_id"] == target
        )
        agent["name"] = name

    def quarantine(self, target, requested_name=None):
        self.calls.append(("quarantine", target, requested_name))
        agent = next(
            agent
            for agent in self.agents
            if agent["name"] == target or agent["pane_id"] == target
        )
        agent["name"] = f"orphan_{requested_name or target}"


class PartialStartClient(FakeClient):
    def __init__(self):
        super().__init__()
        self.created_panes = []
        self.hidden_started = []
        self.fail_first_start = True

    def create_panes(self, count, cwd):
        panes = super().create_panes(count, cwd)
        self.created_panes.extend(panes)
        return panes

    def list_agents(self):
        self.calls.append(("list",))
        if self.hidden_started:
            self.agents.extend(self.hidden_started)
            self.hidden_started = []
        return list(self.agents)

    def start_workers(self, workers):
        if self.fail_first_start:
            self.calls.append(("start_workers", workers))
            self.fail_first_start = False
            for worker in workers[:2]:
                self.hidden_started.append(
                    live_agent(
                        worker["name"],
                        worker["pane_id"],
                        f"late-session-{worker['slot'].lower()}",
                    )
                )
            raise PoolError('{"kind": "agent_pane_busy"}')
        return super().start_workers(workers)


class BusyStartClient(HerdrClient):
    def __init__(self, busy_before_success: int | None):
        super().__init__("w6:p1")
        self.busy_before_success = busy_before_success
        self.calls = []
        self.sleeps = []
        self.now = 0.0

    def _run(self, args):
        self.calls.append(list(args))
        if (
            self.busy_before_success is None
            or len(self.calls) <= self.busy_before_success
        ):
            raise PoolError(
                '{"kind": "agent_pane_busy", "message": "pane is not ready"}'
            )
        return {
            "result": {
                "agent": live_agent(
                    args[2],
                    args[6],
                    f"session-{args[2]}",
                ),
                "argv": [
                    "codex",
                    "--yolo",
                    "--model",
                    "gpt-5.5",
                    "-c",
                    'model_reasoning_effort="medium"',
                ],
            }
        }

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


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
            controller_scope="aaaaaaaa",
        )

    def pool_for_scope(self, client, scope):
        return WorkerPool(
            client=client,
            state_path=default_state_path("w6", scope, root=Path(self.tempdir.name)),
            workspace_id="w6",
            anchor_pane_id="w6:p1",
            controller_scope=scope,
        )

    def write_legacy_pool_state(self, agents):
        workers = []
        for slot, agent in zip(("P2", "P3", "P4"), agents):
            workers.append(
                {
                    "slot": slot,
                    "name": f"hdr_{slot.lower()}",
                    "pane_id": agent["pane_id"],
                    "workspace_id": agent["workspace_id"],
                    "terminal_id": agent["terminal_id"],
                    "session_id": agent["agent_session"]["value"],
                    "input_ready": True,
                    "rebind_pending": False,
                }
            )
        self.state_path.write_text(
            json_state(
                {
                    "schema_version": "herdr-worker-pool/v1",
                    "herdr_session_key": "unspecified",
                    "workspace_id": "w6",
                    "anchor_pane_id": "w6:p1",
                    "contract_id": "contract-a",
                    "root": str(Path("/tmp/project").resolve()),
                    "workers": workers,
                }
            ),
            encoding="utf-8",
        )

    def test_first_prepare_creates_three_yolo_medium_workers(self):
        client = FakeClient()

        result = self.pool(client).prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(result["action"], "created")
        self.assertEqual([worker["slot"] for worker in result["workers"]], ["P2", "P3", "P4"])
        starts = next(call[1] for call in client.calls if call[0] == "start_workers")
        self.assertEqual(len(starts), 3)
        self.assertEqual(
            [worker["name"] for worker in starts],
            ["p2_worker_ready", "p3_worker_ready", "p4_worker_ready"],
        )
        self.assertTrue(all(worker["pane_id"].startswith("w6:p") for worker in starts))

    def test_start_worker_retries_transient_busy_shell_before_success(self):
        client = BusyStartClient(busy_before_success=3)

        with (
            patch("scripts.manage_worker_pool.time.monotonic", client.monotonic),
            patch("scripts.manage_worker_pool.time.sleep", client.sleep),
        ):
            result = client._start_worker(
                {"slot": "P4", "name": "p4_worker_ready", "pane_id": "w6:p1C"}
            )

        self.assertEqual(len(client.calls), 4)
        self.assertEqual(len(client.sleeps), 3)
        self.assertTrue(all(delay == 0.05 for delay in client.sleeps))
        argv = " ".join(result["argv"])
        self.assertIn("--yolo", argv)
        self.assertIn("--model gpt-5.5", argv)
        self.assertIn('model_reasoning_effort="medium"', argv)
        self.assertTrue(all(call[6] == "w6:p1C" for call in client.calls))

    def test_start_worker_busy_timeout_is_bounded_and_fails_closed(self):
        client = BusyStartClient(busy_before_success=None)

        with (
            patch("scripts.manage_worker_pool.time.monotonic", client.monotonic),
            patch("scripts.manage_worker_pool.time.sleep", client.sleep),
            patch("scripts.manage_worker_pool.START_WORKER_BUSY_TIMEOUT", 0.12),
            patch("scripts.manage_worker_pool.START_WORKER_BUSY_BACKOFF", 0.05),
            self.assertRaisesRegex(PoolError, "agent_pane_busy"),
        ):
            client._start_worker(
                {"slot": "P4", "name": "p4_worker_ready", "pane_id": "w6:p1C"}
            )

        self.assertGreaterEqual(client.now, 0.12)
        self.assertLess(client.now, 0.17)
        self.assertEqual(len(client.calls), len(client.sleeps) + 1)
        self.assertTrue(all(call[2] == "p4_worker_ready" for call in client.calls))

    def test_first_prepare_uses_visible_ready_names(self):
        result = self.pool(FakeClient()).prepare(
            "contract-a",
            "/tmp/project",
            3,
        )

        self.assertEqual(
            [worker["name"] for worker in result["workers"]],
            [
                "p2_worker_ready",
                "p3_worker_ready",
                "p4_worker_ready",
            ],
        )

    def test_prepare_migrates_legacy_worker_names_without_new_sessions(self):
        client = FakeClient(
            [
                live_agent("hdr_p2", "w6:p3", "session-p2"),
                live_agent(
                    "hdr_p3",
                    "w6:p4",
                    "session-p3",
                    status="working",
                ),
                live_agent("hdr_p4", "w6:p5", "session-p4"),
            ]
        )
        self.write_legacy_pool_state(client.agents)

        result = self.pool(client).prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(result["action"], "rebound")
        self.assertEqual(
            [worker["name"] for worker in result["workers"]],
            [
                "p2_worker_ready",
                "p3_worker_ready",
                "p4_worker_ready",
            ],
        )
        self.assertEqual(
            [worker["session_id"] for worker in result["workers"]],
            ["session-p2", "session-p3", "session-p4"],
        )
        self.assertFalse(any(call[0] == "start_workers" for call in client.calls))
        self.assertFalse(any(call[0] == "reset" for call in client.calls))

    def test_prepare_reconciles_assigned_name_by_stable_session(self):
        client = FakeClient()
        pool = self.pool(client)
        first = pool.prepare("contract-a", "/tmp/project", 3)
        worker = first["workers"][0]
        client.rename_agent(worker["name"], "p2_impl_auth")

        result = pool.prepare("contract-a", "/tmp/project", 3)

        rebound = result["workers"][0]
        self.assertEqual(rebound["name"], "p2_impl_auth")
        self.assertEqual(rebound["session_id"], worker["session_id"])

    def test_new_contract_resets_then_restores_ready_names(self):
        client = FakeClient()
        pool = self.pool(client)
        first = pool.prepare("contract-a", "/tmp/project-a", 3)
        client.rename_agent(first["workers"][0]["name"], "p2_impl_auth")

        result = pool.prepare("contract-b", "/tmp/project-b", 3)

        self.assertEqual(result["action"], "reset")
        self.assertEqual(
            [worker["name"] for worker in result["workers"]],
            [
                "p2_worker_ready",
                "p3_worker_ready",
                "p4_worker_ready",
            ],
        )

    def test_two_controller_scopes_keep_independent_warm_pools(self):
        client = FakeClient()
        first = self.pool_for_scope(client, "aaaaaaaa").prepare(
            "contract-a",
            "/tmp/project-a",
            3,
        )
        second = self.pool_for_scope(client, "bbbbbbbb").prepare(
            "contract-b",
            "/tmp/project-b",
            3,
        )

        self.assertEqual(len({w["session_id"] for w in first["workers"]}), 3)
        self.assertEqual(len({w["session_id"] for w in second["workers"]}), 3)
        self.assertTrue(
            set(w["name"] for w in first["workers"]).isdisjoint(
                w["name"] for w in second["workers"]
            )
        )
        self.assertFalse(any(call[0] == "reset" for call in client.calls))

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
            [
                ("reset", "p2_worker_ready"),
                ("reset", "p3_worker_ready"),
                ("reset", "p4_worker_ready"),
            ],
        )
        self.assertTrue(all(worker["input_ready"] for worker in result["workers"]))
        self.assertTrue(all(worker["rebind_pending"] for worker in result["workers"]))

    def test_prepare_refuses_to_hijack_busy_worker_for_another_contract(self):
        client = FakeClient()
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project", 3)
        client.agents[1]["agent_status"] = "working"

        with self.assertRaisesRegex(PoolError, "p3_worker_ready.*working"):
            pool.prepare("contract-b", "/tmp/project", 3)

        self.assertFalse(any(call[0] == "reset" for call in client.calls))

    def test_same_contract_controller_attaches_to_busy_workers_in_same_workspace(self):
        client = FakeClient()
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project", 3)
        client.agents[1]["agent_status"] = "working"
        client.calls.clear()

        result = WorkerPool(
            client=client,
            state_path=self.state_path,
            workspace_id="w6",
            anchor_pane_id="w6:p1",
            controller_scope="aaaaaaaa",
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

    def test_same_pool_is_not_reused_by_controller_in_another_workspace(self):
        client = FakeClient()
        self.pool(client).prepare("contract-a", "/tmp/project", 3)
        client.calls.clear()
        moved_controller = WorkerPool(
            client=client,
            state_path=self.state_path,
            workspace_id="w8",
            anchor_pane_id="w8:p1",
            controller_scope="aaaaaaaa",
        )

        with self.assertRaisesRegex(PoolError, "workspace mismatch"):
            moved_controller.prepare("contract-a", "/tmp/project", 3)

        self.assertFalse(any(call[0] in {"reset", "start_workers"} for call in client.calls))

    def test_w6_controller_does_not_adopt_same_socket_w5_workers(self):
        w5_agents = [
            live_agent("hdr_p2", "w5:p2", "session-w5-p2"),
            live_agent("hdr_p3", "w5:p3", "session-w5-p3"),
            live_agent("hdr_p4", "w5:p4", "session-w5-p4"),
        ]
        client = FakeClient(w5_agents)

        result = self.pool(client).prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(result["action"], "created")
        self.assertTrue(all(worker["pane_id"].startswith("w6:p") for worker in result["workers"]))
        self.assertTrue(all(worker["workspace_id"] == "w6" for worker in result["workers"]))
        self.assertTrue(
            {worker["session_id"] for worker in result["workers"]}.isdisjoint(
                {"session-w5-p2", "session-w5-p3", "session-w5-p4"}
            )
        )
        self.assertFalse(any(call[0] == "reset" for call in client.calls))

    def test_unique_legacy_workspace_ledger_is_adopted_in_same_workspace(self):
        client = FakeClient(workspace_id="w5")
        legacy_path = Path(self.tempdir.name) / "w5.json"
        WorkerPool(
            client=client,
            state_path=legacy_path,
            workspace_id="w5",
            anchor_pane_id="w5:p1",
            controller_scope="aaaaaaaa",
        ).prepare("contract-a", "/tmp/project", 3)
        active_path = Path(self.tempdir.name) / "active.json"
        client.calls.clear()

        result = WorkerPool(
            client=client,
            state_path=active_path,
            workspace_id="w5",
            anchor_pane_id="w5:p1",
            controller_scope="aaaaaaaa",
        ).prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(result["action"], "reused")
        self.assertTrue(active_path.is_file())
        self.assertFalse(legacy_path.exists())
        self.assertEqual(client.calls, [("list",)])

    def test_default_pool_ledger_is_workspace_scoped(self):
        with patch.dict(os.environ, {"HERDR_SOCKET_PATH": "/tmp/herdr-a.sock"}):
            first = default_state_path("w6", "aaaaaaaa")
            moved = default_state_path("w8", "aaaaaaaa")
        with patch.dict(os.environ, {"HERDR_SOCKET_PATH": "/tmp/herdr-b.sock"}):
            another_session = default_state_path("w6", "aaaaaaaa")

        self.assertTrue(first.name.startswith("active-"))
        self.assertNotEqual(moved, first)
        self.assertNotEqual(another_session, first)
        self.assertIn("w6", first.name)
        self.assertIn("w8", moved.name)

    def test_default_pool_ledger_is_controller_scope_scoped(self):
        with patch.dict(os.environ, {"HERDR_SOCKET_PATH": "/tmp/herdr-a.sock"}):
            first = default_state_path("w6", "aaaaaaaa")
            second = default_state_path("w6", "bbbbbbbb")

        self.assertNotEqual(second, first)
        self.assertIn("aaaaaaaa", first.name)
        self.assertIn("bbbbbbbb", second.name)

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
        client.agents[1]["pane_id"] = "w6:p9"
        client.agents[1]["workspace_id"] = "w6"
        client.calls.clear()

        result = pool.prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(result["action"], "rebound")
        worker = next(worker for worker in result["workers"] if worker["slot"] == "P3")
        self.assertEqual(worker["pane_id"], "w6:p9")
        self.assertEqual(worker["workspace_id"], "w6")
        self.assertFalse(any(call[0] == "start_workers" for call in client.calls))

    def test_prepare_recreates_only_a_closed_worker(self):
        client = FakeClient()
        pool = self.pool(client)
        original = pool.prepare("contract-a", "/tmp/project", 3)
        original_sessions = {
            worker["slot"]: worker["session_id"] for worker in original["workers"]
        }
        closed = next(worker for worker in original["workers"] if worker["slot"] == "P3")
        client.agents = [
            agent for agent in client.agents if agent["name"] != closed["name"]
        ]
        client.calls.clear()

        result = pool.prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(result["action"], "recovered")
        starts = next(call[1] for call in client.calls if call[0] == "start_workers")
        self.assertEqual([worker["slot"] for worker in starts], ["P3"])
        sessions = {
            worker["slot"]: worker["session_id"] for worker in result["workers"]
        }
        self.assertEqual(sessions["P2"], original_sessions["P2"])
        self.assertEqual(sessions["P4"], original_sessions["P4"])

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
            [worker["slot"] for worker in starts],
            ["P3", "P4"],
        )

    def test_wrong_root_is_rejected_before_recovering_a_closed_worker(self):
        client = FakeClient()
        pool = self.pool(client)
        original = pool.prepare("contract-a", "/tmp/project", 3)
        closed = next(worker for worker in original["workers"] if worker["slot"] == "P3")
        client.agents = [
            agent for agent in client.agents if agent["name"] != closed["name"]
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
        original = pool.prepare("contract-a", "/tmp/project", 3)
        closed = next(worker for worker in original["workers"] if worker["slot"] == "P3")
        client.agents = [
            agent for agent in client.agents if agent["name"] != closed["name"]
        ]
        client.invalid_argv_once = True

        with self.assertRaisesRegex(PoolError, "worker launch invariant failed"):
            pool.prepare("contract-a", "/tmp/project", 3)

        self.assertTrue(any(call[0] == "quarantine" for call in client.calls))
        recovered = pool.prepare("contract-a", "/tmp/project", 3)
        self.assertEqual(recovered["action"], "recovered")
        self.assertTrue(any(worker["slot"] == "P3" for worker in recovered["workers"]))

    def test_partial_initial_start_quarantines_late_live_agents_by_pane_before_retry(self):
        client = PartialStartClient()
        pool = self.pool(client)

        with self.assertRaisesRegex(PoolError, "agent_pane_busy"):
            pool.prepare("contract-a", "/tmp/project", 3)

        self.assertFalse(self.state_path.exists())
        self.assertEqual(
            [call for call in client.calls if call[0] == "quarantine"],
            [
                ("quarantine", "w6:p3", "p2_worker_ready"),
                ("quarantine", "w6:p4", "p3_worker_ready"),
            ],
        )
        self.assertEqual(
            [agent["name"] for agent in client.agents],
            ["orphan_p2_worker_ready", "orphan_p3_worker_ready"],
        )
        self.assertNotIn(("quarantine", "w6:p5", "p4_worker_ready"), client.calls)

        retry = pool.prepare("contract-a", "/tmp/project", 3)

        self.assertEqual(retry["action"], "created")
        self.assertEqual(
            [worker["name"] for worker in retry["workers"]],
            ["p2_worker_ready", "p3_worker_ready", "p4_worker_ready"],
        )


if __name__ == "__main__":
    unittest.main()
