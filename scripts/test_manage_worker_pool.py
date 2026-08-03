import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.manage_worker_pool import HerdrClient, WorkerPool, start_command
from scripts.workspace_state import create_state, load_state, mutate_state, register_lane


def live(
    slot,
    session_id=None,
    *,
    pane=None,
    workspace="w6",
    status="done",
    name=None,
):
    return {
        "name": name or f"p{slot[1:].lower()}_impl",
        "pane_id": pane or f"{workspace}:p{slot[1:]}",
        "workspace_id": workspace,
        "terminal_id": f"term-{pane or f'{workspace}:p{slot[1:]}'}",
        "agent_status": status,
        "agent_session": {"value": session_id} if session_id else None,
    }


class FakeClient:
    def __init__(self):
        self.agents = []
        self.started = []
        self.replacement_slots = []
        self.allocations = []
        self.forbidden = []

    def list_agents(self):
        return list(self.agents)

    def start_agent(self, command, slot):
        self.started.append(command)
        self.replacement_slots.append(slot)

    def allocate_pane(self, workspace_id, anchor_pane_id, cwd):
        self.allocations.append((workspace_id, anchor_pane_id, str(cwd)))
        return f"{workspace_id}:p9"

    def run(self, command):
        if command[:2] == ["pane", "close"]:
            self.forbidden.append(command)
        if command[:2] == ["agent", "move"]:
            self.forbidden.append(command)
        if command[:2] == ["agent", "rename"]:
            self.forbidden.append(command)

    def prompts_to_workspace(self, workspace_id):
        return [
            command for command in self.forbidden
            if any(str(part).startswith(f"{workspace_id}:") for part in command)
        ]


class WorkerPoolTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "workspace-state.json"
        create_state(
            self.path,
            "w6",
            controller={"role_name": "p1_orchestrator", "pane_id": "w6:p1"},
            run={
                "contract_id": "contract-a",
                "controller_session_id": "controller-session",
                "run_dir": self.tempdir.name,
                "root": self.tempdir.name,
            },
        )
        self.client = FakeClient()
        self.pool = WorkerPool(self.client, self.path, "w6")

    def tearDown(self):
        self.tempdir.cleanup()

    def seed_bound_slot(
        self,
        slot,
        session_id,
        pane,
        *,
        generation=1,
        lane_id="lane-a",
        state="ACTIVE",
    ):
        register_lane(
            self.path,
            {
                "lane_id": lane_id,
                "generation": generation,
                "state": state,
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

    def seed_three_busy_slots(self):
        for slot in ("P2", "P3", "P4"):
            self.seed_bound_slot(
                slot,
                f"session-{slot.lower()}",
                f"w6:p{slot[1:]}",
                lane_id=f"lane-{slot.lower()}",
            )

    def persist_valid_receipt(self, lane, generation):
        receipt = {
            "schema_version": "herdr-lane-receipt/v1",
            "contract_id": "contract-a",
            "lane_id": lane,
            "generation": generation,
            "session_id": "session-2",
            "status": "PASS",
            "input_identity": {},
            "output_artifact": {"commit_sha": "abc123"},
            "verification": {
                "covered_acceptance": ["focused"],
                "checks": [{"command": "unit", "result": "pass"}],
            },
            "finding_or_blocker": None,
            "resume_condition": None,
        }
        receipt_path = Path(load_state(self.path)["lanes"][lane]["receipt_path"])
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    def persist_matching_git_artifact(self, lane, generation):
        def mutate(value):
            value["lanes"][lane]["output_artifact"] = {
                "commit_sha": f"artifact-{generation}"
            }

        mutate_state(self.path, mutate)

    def assert_no_forbidden_pane_mutation(self):
        self.assertEqual([], self.client.forbidden)

    def test_cold_start_allocates_local_no_focus_pane_and_uses_current_cli(self):
        self.pool.ensure(["P2"])

        self.assertEqual(
            [("w6", "w6:p1", self.tempdir.name)],
            self.client.allocations,
        )
        self.assertEqual(
            [
                "herdr", "agent", "start", "p2_impl", "--kind", "codex",
                "--pane", "w6:p9", "--", "--yolo", "-m", "gpt-5.5",
                "-c", "model_reasoning_effort=high",
            ],
            self.client.started[0],
        )
        self.assert_no_forbidden_pane_mutation()

    def test_start_command_uses_native_yolo_for_implementation_slots(self):
        try:
            command = start_command("P3", "w6", set(), "w6:p9")
        except TypeError as error:
            self.fail(f"start_command lacks the explicit pane boundary: {error}")
        self.assertEqual(
            [
                "herdr", "agent", "start", "p3_impl", "--kind", "codex",
                "--pane", "w6:p9", "--", "--yolo", "-m", "gpt-5.5",
                "-c", "model_reasoning_effort=high",
            ],
            command,
        )

    def test_installed_herdr_help_requires_name_kind_and_existing_pane(self):
        result = subprocess.run(
            ["herdr", "agent", "start", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        help_text = result.stdout + result.stderr
        self.assertIn("herdr agent start <NAME> --kind <KIND> --pane <ID>", help_text)

    def test_live_adapter_splits_from_local_anchor_without_focus(self):
        calls = []
        client = HerdrClient()

        def run(args):
            calls.append(args)
            return {
                "result": {
                    "pane": {"pane_id": "w6:p9", "workspace_id": "w6"}
                }
            }

        client._run = run
        try:
            pane_id = client.allocate_pane("w6", "w6:p1", Path("/run/root"))
        except AttributeError as error:
            self.fail(f"live adapter lacks local pane allocation: {error}")

        self.assertEqual("w6:p9", pane_id)
        self.assertEqual(
            [[
                "pane", "split", "--pane", "w6:p1", "--direction", "right",
                "--cwd", "/run/root", "--no-focus",
            ]],
            calls,
        )
        self.assertFalse(any("close" in command or "move" in command for command in calls))

    def test_cold_worker_binds_session_only_after_first_prompt(self):
        self.pool.ensure(["P2"])
        self.assertIsNone(load_state(self.path)["slots"]["P2"]["session_id"])

        self.client.agents = [live("P2", session_id="new-session")]
        self.pool.reconcile()

        self.assertEqual(
            "new-session", load_state(self.path)["slots"]["P2"]["session_id"]
        )

    def test_same_workspace_move_preserves_generation(self):
        self.seed_bound_slot("P2", "session-2", "w6:p2", generation=3)
        self.client.agents = [
            live("P2", "session-2", pane="w6:p9", workspace="w6")
        ]

        self.pool.reconcile()

        state = load_state(self.path)
        self.assertEqual("w6:p9", state["slots"]["P2"]["pane_id"])
        self.assertEqual(3, state["lanes"]["lane-a"]["generation"])

    def test_three_misses_replace_only_lost_lane(self):
        self.seed_three_busy_slots()
        self.client.agents = [live("P3", "session-p3"), live("P4", "session-p4")]

        for _ in range(3):
            self.pool.reconcile()

        state = load_state(self.path)
        self.assertEqual("SUPERSEDED", state["lanes"]["lane-p2"]["state"])
        self.assertEqual("ACTIVE", state["lanes"]["lane-p3"]["state"])
        self.assertEqual("ACTIVE", state["lanes"]["lane-p4"]["state"])
        self.assertEqual(["P2"], self.client.replacement_slots)
        self.assert_no_forbidden_pane_mutation()

    def test_foreign_workspace_session_is_never_adopted(self):
        self.seed_bound_slot("P2", "session-2", "w6:p2")
        self.client.agents = [
            live("P2", "session-2", pane="w7:p2", workspace="w7")
        ]

        for _ in range(3):
            self.pool.reconcile()

        self.assertNotEqual(
            "w7:p2", load_state(self.path)["slots"]["P2"]["pane_id"]
        )
        self.assertEqual([], self.client.prompts_to_workspace("w7"))

    def test_valid_receipt_wins_when_worker_disappears(self):
        self.seed_bound_slot("P2", "session-2", "w6:p2", generation=2)
        self.persist_valid_receipt("lane-a", generation=2)
        self.client.agents = []

        for _ in range(3):
            self.pool.reconcile()

        state = load_state(self.path)
        self.assertEqual("ACCEPTED", state["lanes"]["lane-a"]["state"])
        self.assertEqual([], self.client.replacement_slots)

    def test_full_herdr_restart_discards_live_sessions_only(self):
        self.seed_bound_slot("P2", "old-session", "w6:p2", generation=2)
        self.persist_matching_git_artifact("lane-a", generation=2)

        self.pool.reconcile(restart_detected=True)

        state = load_state(self.path)
        self.assertIsNone(state["slots"]["P2"]["session_id"])
        self.assertEqual("REUSABLE", state["lanes"]["lane-a"]["artifact_state"])
        self.assertNotEqual(
            "old-session", state["run"].get("controller_session_id")
        )


if __name__ == "__main__":
    unittest.main()
