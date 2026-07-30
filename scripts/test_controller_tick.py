import unittest

from scripts.controller_tick import controller_tick
from scripts.workspace_state import initial_state


def request(request_id, paths):
    return {
        "request_id": request_id,
        "summary": request_id,
        "affected_paths": paths,
        "dependencies": [],
    }


def state_with_free_slots(*slots):
    state = initial_state(
        "w6",
        controller={"role_name": "p1_orchestrator",
                    "session_id": "controller-session"},
    )
    for slot in slots:
        state["slots"][slot]["status"] = "IDLE"
        state["slots"][slot]["session_id"] = f"{slot.lower()}-session"
    return state


def busy_state(heartbeat_at=None, wake_verified_at=None):
    state = state_with_free_slots("P2", "P3", "P4")
    for slot in ("P2", "P3", "P4"):
        state["slots"][slot]["status"] = "BUSY"
    state["run"] = {"status": "ACTIVE"}
    state["watcher"]["heartbeat_at"] = heartbeat_at
    state["watcher"]["wake_verified_at"] = wake_verified_at
    return state


class ControllerTickTests(unittest.TestCase):
    def test_tick_emits_all_ready_work_in_one_return(self):
        result = controller_tick(
            state_with_free_slots("P2", "P3", "P4"),
            requests=[
                request("a", ["a/**"]),
                request("b", ["b/**"]),
                request("c", ["c/**"]),
            ],
            events=[],
            live_agents=[],
            now=100,
        )

        self.assertEqual(
            [
                ("DISPATCH", "P2"),
                ("DISPATCH", "P3"),
                ("DISPATCH", "P4"),
            ],
            [(item["kind"], item["slot"]) for item in result["actions"]],
        )

    def test_nonterminal_reducer_return_is_not_assistant_final(self):
        result = controller_tick(
            busy_state(), requests=[], events=[], live_agents=[], now=100
        )

        self.assertFalse(result["assistant_may_finalize"])
        self.assertEqual("MONITOR", result["actions"][0]["kind"])

    def test_missing_wake_proof_forces_bounded_monitoring(self):
        state = busy_state(
            heartbeat_at=99,
            wake_verified_at=None,
        )

        result = controller_tick(
            state, requests=[], events=[], live_agents=[], now=100
        )

        self.assertEqual("MONITOR", result["actions"][0]["kind"])
        self.assertFalse(result["may_yield"])

    def test_verified_wake_allows_yield_without_finalizing(self):
        state = busy_state(
            heartbeat_at=99,
            wake_verified_at=98,
        )

        result = controller_tick(
            state, requests=[], events=[], live_agents=[], now=100
        )

        self.assertEqual("YIELD", result["actions"][0]["kind"])
        self.assertTrue(result["may_yield"])
        self.assertFalse(result["assistant_may_finalize"])

    def test_terminal_delivery_may_finalize(self):
        state = state_with_free_slots()
        state["run"] = {"status": "ACTIVE"}
        state["lanes"] = {
            "a": {"state": "ACCEPTED"},
            "b": {"state": "BLOCKED"},
        }

        result = controller_tick(
            state, requests=[], events=[], live_agents=[], now=100
        )

        self.assertTrue(result["assistant_may_finalize"])


if __name__ == "__main__":
    unittest.main()
