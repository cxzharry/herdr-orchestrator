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


def active_lane(lane_id, slot, started_at=0, progress_at=None):
    lane = {
        "lane_id": lane_id,
        "generation": 1,
        "state": "ACTIVE",
        "slot": slot,
        "agent_name": f"p{slot[1:].lower()}_impl",
        "session_id": f"{slot.lower()}-session",
        "pane_id": f"w6:p{slot[1:]}",
        "owned_scope": [f"{lane_id}/**"],
        "started_at": started_at,
        "active_timer_started_at": started_at,
    }
    if progress_at is not None:
        lane["last_progress_at"] = progress_at
    return lane


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


def standard_state_with_free_slots(*slots):
    state = state_with_free_slots(*slots)
    state["run"] = {"mode": "Standard", "status": "ACTIVE"}
    return state


def ready_qc_lane(lane_id, slot):
    return {
        "lane_id": lane_id,
        "state": "READY",
        "input_identity": {"candidate_commit": "candidate-abc"},
        "agent_name": {
            "P7": "p7_qc",
            "P8": "p8_design",
            "P9": "p9_persona",
        }[slot],
    }


def standard_state_ready_for_qc(applicability):
    state = standard_state_with_free_slots()
    state["run"]["review_applicability"] = applicability
    state["lanes"] = {
        "integration": {
            "state": "ACCEPTED",
            "output_artifact": {"commit": "candidate-abc"},
        },
        "independent_review": {
            "state": "PASS",
            "input_identity": {"candidate_commit": "candidate-abc"},
        },
        "functional_qc": ready_qc_lane("functional_qc", "P7"),
        "design_qc": ready_qc_lane("design_qc", "P8"),
        "persona_qc": ready_qc_lane("persona_qc", "P9"),
    }
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

    def test_standard_tick_prewarms_p5_p6_with_implementation_dispatch(self):
        state = standard_state_with_free_slots("P2", "P3", "P4", "P5", "P6")

        result = controller_tick(
            state,
            requests=[request("a", ["a/**"]), request("b", ["b/**"])],
            events=[],
            live_agents=[],
            now=10,
        )

        self.assertEqual(
            [("DISPATCH", "P2"), ("DISPATCH", "P3"), ("PREWARM", "P5"), ("PREWARM", "P6")],
            [(item["kind"], item["slot"]) for item in result["actions"]],
        )

    def test_first_active_implementation_tick_prewarms_p5_p6_for_both_modes(self):
        for mode in ("Compact", "Standard"):
            with self.subTest(mode=mode):
                state = state_with_free_slots("P6")
                state["run"] = {"mode": mode, "status": "ACTIVE"}
                state["lanes"] = {
                    "active": active_lane("active", "P3"),
                }

                result = controller_tick(
                    state, requests=[], events=[], live_agents=[], now=10
                )

                self.assertEqual(
                    [("PREWARM", "P5"), ("PREWARM", "P6")],
                    [(item["kind"], item.get("slot")) for item in result["actions"]],
                )
                self.assertEqual("WARMING", result["state"]["slots"]["P5"]["status"])
                self.assertEqual("WARMING", result["state"]["slots"]["P6"]["status"])

    def test_standard_tick_dispatches_all_applicable_ready_qc_lanes(self):
        state = standard_state_ready_for_qc(
            {"P7": True, "P8": True, "P9": True}
        )

        result = controller_tick(
            state, requests=[], events=[], live_agents=[], now=10
        )

        self.assertEqual(
            [
                ("DISPATCH", "P7", "functional_qc"),
                ("DISPATCH", "P8", "design_qc"),
                ("DISPATCH", "P9", "persona_qc"),
            ],
            [
                (item["kind"], item.get("slot"), item.get("lane_id"))
                for item in result["actions"]
            ],
        )
        self.assertEqual("ACTIVE", result["state"]["lanes"]["functional_qc"]["state"])
        self.assertEqual("ACTIVE", result["state"]["lanes"]["design_qc"]["state"])
        self.assertEqual("ACTIVE", result["state"]["lanes"]["persona_qc"]["state"])
        self.assertEqual("READY", state["lanes"]["functional_qc"]["state"])

    def test_standard_tick_skips_non_applicable_ready_qc_lanes(self):
        state = standard_state_ready_for_qc(
            {"P7": True, "P8": False, "P9": True}
        )

        result = controller_tick(
            state, requests=[], events=[], live_agents=[], now=10
        )

        self.assertEqual(
            ["P7", "P9"],
            [item.get("slot") for item in result["actions"]],
        )
        self.assertEqual("READY", result["state"]["lanes"]["design_qc"]["state"])

    def test_standard_tick_waits_when_review_is_not_for_exact_integration(self):
        state = standard_state_ready_for_qc(
            {"P7": True, "P8": False, "P9": False}
        )
        state["lanes"]["integration"]["output_artifact"]["commit"] = "candidate-new"
        state["lanes"]["independent_review"]["input_identity"]["candidate_commit"] = (
            "candidate-old"
        )

        result = controller_tick(
            state, requests=[], events=[], live_agents=[], now=10
        )

        self.assertEqual("MONITOR", result["actions"][0]["kind"])
        self.assertEqual("READY", result["state"]["lanes"]["functional_qc"]["state"])

    def test_standard_tick_keeps_stale_or_unbound_qc_lanes_ready(self):
        for candidate in ("candidate-old", None):
            with self.subTest(candidate=candidate):
                state = standard_state_ready_for_qc(
                    {"P7": True, "P8": False, "P9": False}
                )
                lane = state["lanes"]["functional_qc"]
                if candidate is None:
                    lane.pop("input_identity")
                else:
                    lane["input_identity"]["candidate_commit"] = candidate

                result = controller_tick(
                    state, requests=[], events=[], live_agents=[], now=10
                )

                self.assertEqual("MONITOR", result["actions"][0]["kind"])
                self.assertEqual(
                    "READY", result["state"]["lanes"]["functional_qc"]["state"]
                )

    def test_reviewer_can_inspect_completed_lane_while_sibling_runs(self):
        state = standard_state_with_free_slots("P6")
        state["lanes"] = {
            "done-a": {"state": "ACCEPTED", "output_artifact": {"commit": "abc"}},
            "active-b": active_lane("active-b", "P3", started_at=0, progress_at=95),
        }

        result = controller_tick(
            state, requests=[], events=[], live_agents=[], now=100
        )

        self.assertIn(
            {"kind": "REVIEW_DIFF", "slot": "P6", "lane_id": "done-a"},
            result["actions"],
        )
        self.assertFalse(result["assistant_may_finalize"])

    def test_stall_redirects_without_resetting_original_timer(self):
        state = state_with_free_slots()
        state["lanes"] = {
            "stalled": active_lane("stalled", "P4", started_at=0),
        }

        result = controller_tick(
            state, requests=[], events=[], live_agents=[], now=60
        )

        self.assertEqual(
            {
                "kind": "REDIRECT",
                "lane_id": "stalled",
                "slot": "P4",
                "deadline_seconds": 60,
                "timer_started_at": 0,
            },
            result["actions"][0],
        )
        self.assertEqual(0, result["state"]["lanes"]["stalled"]["active_timer_started_at"])

    def test_stall_redirect_is_not_repeated_before_reassign_deadline(self):
        state = state_with_free_slots()
        state["lanes"] = {
            "stalled": active_lane("stalled", "P4", started_at=0),
        }

        first = controller_tick(
            state, requests=[], events=[], live_agents=[], now=60
        )
        second = controller_tick(
            first["state"], requests=[], events=[], live_agents=[], now=61
        )

        self.assertEqual("REDIRECT", first["actions"][0]["kind"])
        self.assertEqual("MONITOR", second["actions"][0]["kind"])
        self.assertEqual(0, second["state"]["lanes"]["stalled"]["active_timer_started_at"])

    def test_stall_reassigns_to_idle_compatible_slot_and_prevents_duplicate_writes(self):
        state = state_with_free_slots("P2")
        state["slots"]["P2"].update(
            {
                "pane_id": "w6:p2",
                "workspace_id": "w6",
                "role_name": "p2_impl",
            }
        )
        state["slots"]["P4"].update(
            {
                "status": "BUSY",
                "session_id": "p4-session",
                "pane_id": "w6:p4",
                "workspace_id": "w6",
            }
        )
        state["lanes"] = {
            "stalled": {
                **active_lane("stalled", "P4", started_at=0),
                "agent_name": "p4_impl",
                "session_id": "p4-session",
                "pane_id": "w6:p4",
            },
        }

        result = controller_tick(
            state, requests=[], events=[], live_agents=[], now=120
        )

        self.assertEqual("REASSIGN", result["actions"][0]["kind"])
        self.assertEqual("stalled", result["actions"][0]["lane_id"])
        self.assertEqual("P4", result["actions"][0]["from_slot"])
        self.assertEqual("P2", result["actions"][0]["to_slot"])
        self.assertEqual(0, result["actions"][0]["timer_started_at"])
        self.assertTrue(result["actions"][0]["ownership_transfer"]["duplicate_writes_prevented"])
        self.assertEqual("SUPERSEDED", result["state"]["lanes"]["stalled"]["state"])
        replacement = result["state"]["lanes"]["stalled-reassigned-g2"]
        self.assertEqual("ACTIVE", replacement["state"])
        self.assertEqual("p2_impl", replacement["agent_name"])
        self.assertEqual("p2-session", replacement["session_id"])
        self.assertEqual("w6:p2", replacement["pane_id"])
        self.assertEqual(0, replacement["active_timer_started_at"])
        self.assertEqual("IDLE", result["state"]["slots"]["P4"]["status"])

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
