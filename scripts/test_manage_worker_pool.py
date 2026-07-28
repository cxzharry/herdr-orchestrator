import tempfile
import unittest
from pathlib import Path

from scripts.manage_worker_pool import PoolError, WorkerPool


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
        "agent_status": status,
        "agent_session": {"value": session},
    }


class FakeClient:
    def __init__(
        self,
        agents=None,
        sessions_on_start=True,
        sessions_on_reset=True,
    ):
        self.agents = list(agents or [])
        self.calls = []
        self.sessions_on_start = sessions_on_start
        self.sessions_on_reset = sessions_on_reset

    def list_agents(self):
        self.calls.append(("list",))
        return list(self.agents)

    def create_panes(self, count, cwd):
        self.calls.append(("create_panes", count, cwd))
        return [f"w6:p{index + 3}" for index in range(count)]

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

    def test_prepare_refuses_to_hijack_busy_worker(self):
        client = FakeClient()
        pool = self.pool(client)
        pool.prepare("contract-a", "/tmp/project", 3)
        client.agents[1]["agent_status"] = "working"

        with self.assertRaisesRegex(PoolError, "hdr_p3.*working"):
            pool.prepare("contract-a", "/tmp/project", 3)

        self.assertFalse(any(call[0] == "reset" for call in client.calls))

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


if __name__ == "__main__":
    unittest.main()
