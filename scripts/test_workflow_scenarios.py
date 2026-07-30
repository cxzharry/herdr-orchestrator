import copy
import tempfile
import unittest
from pathlib import Path

from scripts.controller_router import ControllerRouter
from scripts.controller_tick import controller_tick
from scripts.manage_worker_pool import WorkerPool
from scripts.run_watcher import run_once
from scripts.workspace_state import create_state, load_state, mutate_state, register_lane


def live(slot, session_id=None, *, pane=None, workspace="w6", status="done"):
    return {
        "name": f"p{slot[1:].lower()}_impl",
        "pane_id": pane or f"{workspace}:p{slot[1:]}",
        "workspace_id": workspace,
        "terminal_id": f"term-{slot}",
        "agent_status": status,
        "agent_session": {"value": session_id} if session_id else None,
    }


def request(request_id, paths):
    return {
        "request_id": request_id,
        "summary": request_id,
        "affected_paths": paths,
        "dependencies": [],
    }


class ScenarioHerdr:
    def __init__(self, workspace_id):
        self.workspace_id = workspace_id
        self.agents = []
        self.started = []
        self.prompts = []
        self.signals = []
        self.closed = []

    def list_agents(self):
        return copy.deepcopy(self.agents)

    def start_agent(self, command, *_):
        self.started.append(command)

    def prompt_agent(self, target, capsule):
        self.prompts.append((target, capsule))

    def signal_agent(self, target, value):
        self.signals.append((target, value))

    def close_pane(self, pane):
        self.closed.append(pane)
        raise AssertionError("runtime must never close a user pane")


class WorkflowScenarioTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "workspace-state.json"
        create_state(
            self.path,
            "w6",
            controller={"role_name": "p1_orchestrator",
                        "session_id": "controller-session"},
            run={"contract_id": "contract-a", "run_dir": self.tempdir.name},
        )
        self.adapter = ScenarioHerdr("w6")

    def tearDown(self):
        self.tempdir.cleanup()

    def pool(self):
        return WorkerPool(self.adapter, self.path, "w6")

    def seed_bound_slot(self, slot, session_id, pane, *, lane_id="lane-a", generation=1):
        register_lane(
            self.path,
            {
                "lane_id": lane_id,
                "generation": generation,
                "state": "ACTIVE",
                "session_id": session_id,
                "agent_name": f"p{slot[1:].lower()}_impl",
            },
        )

        def mutate(value):
            value["slots"][slot].update(
                {
                    "session_id": session_id,
                    "pane_id": pane,
                    "workspace_id": "w6",
                    "status": "BUSY",
                    "lane_id": lane_id,
                    "generation": generation,
                    "misses": 0,
                }
            )

        mutate_state(self.path, mutate)

    def test_cold_p2_p4_first_prompt_then_session_bind(self):
        self.pool().ensure(["P2", "P3", "P4"])
        self.assertEqual(["p2_impl", "p3_impl", "p4_impl"], [cmd[4] for cmd in self.adapter.started])
        self.assertIsNone(load_state(self.path)["slots"]["P2"]["session_id"])

        self.adapter.agents = [
            live("P2", "session-2"),
            live("P3", "session-3"),
            live("P4", "session-4"),
        ]
        self.pool().reconcile()

        state = load_state(self.path)
        self.assertEqual("session-2", state["slots"]["P2"]["session_id"])
        self.assertEqual("session-3", state["slots"]["P3"]["session_id"])
        self.assertEqual("session-4", state["slots"]["P4"]["session_id"])
        self.assertEqual([], self.adapter.closed)

    def test_disjoint_request_dispatches_while_workers_busy(self):
        controller = {
            "name": "p1_orchestrator",
            "pane_id": "w6:p1",
            "workspace_id": "w6",
            "terminal_id": "term-p1",
            "agent_status": "idle",
            "agent_session": {"value": "controller-session"},
        }
        worker = live("P2", "session-2")
        router = ControllerRouter(self.adapter, self.path, "w6")
        router.forward_request(
            worker,
            controller,
            {"summary": "b", "affected_paths": ["b/**"], "dependencies": []},
        )

        state = load_state(self.path)
        for slot in ("P2", "P3", "P4"):
            state["slots"][slot]["status"] = "IDLE"
            state["slots"][slot]["session_id"] = f"{slot.lower()}-session"
        result = controller_tick(
            state,
            requests=[request("a", ["a/**"]), *router.inbox_requests()],
            events=[],
            live_agents=[],
            now=100,
        )

        self.assertEqual(["DISPATCH", "DISPATCH"], [item["kind"] for item in result["actions"]])
        self.assertEqual([], self.adapter.closed)

    def test_same_workspace_move_preserves_lane_and_generation(self):
        self.seed_bound_slot("P2", "session-2", "w6:p2", generation=3)
        self.adapter.agents = [live("P2", "session-2", pane="w6:p9")]

        self.pool().reconcile()

        state = load_state(self.path)
        self.assertEqual("w6:p9", state["slots"]["P2"]["pane_id"])
        self.assertEqual(3, state["lanes"]["lane-a"]["generation"])
        self.assertEqual([], self.adapter.closed)

    def test_closed_worker_replaces_only_lost_lane(self):
        for slot in ("P2", "P3", "P4"):
            self.seed_bound_slot(
                slot,
                f"session-{slot.lower()}",
                f"w6:p{slot[1:]}",
                lane_id=f"lane-{slot.lower()}",
            )
        self.adapter.agents = [live("P3", "session-p3"), live("P4", "session-p4")]

        for _ in range(3):
            self.pool().reconcile()

        state = load_state(self.path)
        self.assertEqual("SUPERSEDED", state["lanes"]["lane-p2"]["state"])
        self.assertEqual("ACTIVE", state["lanes"]["lane-p3"]["state"])
        self.assertEqual("ACTIVE", state["lanes"]["lane-p4"]["state"])
        self.assertEqual(["p2_impl"], [cmd[4] for cmd in self.adapter.started])
        self.assertEqual([], self.adapter.closed)

    def test_foreign_workspace_agent_is_never_adopted(self):
        self.seed_bound_slot("P2", "session-2", "w6:p2")
        self.adapter.agents = [live("P2", "session-2", pane="w7:p2", workspace="w7")]

        for _ in range(3):
            self.pool().reconcile()

        self.assertNotEqual("w7:p2", load_state(self.path)["slots"]["P2"]["pane_id"])
        self.assertEqual([], [item for item in self.adapter.prompts if "w7" in str(item)])
        self.assertEqual([], self.adapter.closed)

    def test_missing_watcher_proof_prevents_early_final(self):
        self.seed_bound_slot("P2", "session-2", "w6:p2")
        run_once(self.path, self.adapter, now=100)
        state = load_state(self.path)
        state["run"] = {"status": "ACTIVE"}
        for slot in ("P2", "P3", "P4"):
            state["slots"][slot]["status"] = "BUSY"

        result = controller_tick(
            state,
            requests=[],
            events=state["events"],
            live_agents=[],
            now=101,
        )

        self.assertEqual("MONITOR", result["actions"][0]["kind"])
        self.assertFalse(result["assistant_may_finalize"])
        self.assertFalse(result["may_yield"])
        self.assertEqual([], self.adapter.closed)


if __name__ == "__main__":
    unittest.main()
