import json
import tempfile
import unittest
from pathlib import Path

from scripts.assign_agent_name import (
    AssignmentError,
    assign_lane_name,
    migrate_legacy_lane_names,
)
from scripts.runtime_registry import RuntimeRegistry
from scripts.scheduler_state import SchedulerStateError, set_lane


class FakeHerdr:
    def __init__(self, agents, on_rename=None, after_rename=None):
        self.agents = agents
        self.calls = []
        self.on_rename = on_rename
        self.after_rename = after_rename

    def list_agents(self):
        return list(self.agents)

    def rename_agent(self, pane_id, name):
        self.calls.append(("rename", pane_id, name))
        agent = next(agent for agent in self.agents if agent["pane_id"] == pane_id)
        agent["name"] = name
        if self.on_rename is not None:
            self.on_rename()
        if self.after_rename is not None:
            self.after_rename(self)


class AssignAgentNameTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.path = self.root / "control-state.json"
        self.lane = {
            "lane_id": "auth-api",
            "generation": 1,
            "slot": "P2",
            "role": "implementation",
            "display_role": "impl",
            "display_slug": "auth",
            "agent_name": "p2_worker_ready",
            "dispatch_agent_name": "p2_worker_ready",
            "pane_id": "w1:p2",
            "session_id": "session-p2",
            "input_identity": {"base_sha": "abc"},
            "receipt_path": str(self.root / "receipt.json"),
        }
        self.write_state("scope-a", {"auth-api": self.lane})

    def tearDown(self):
        self.tempdir.cleanup()

    def write_state(self, scope, lanes, path=None):
        (path or self.path).write_text(
            json.dumps(
                {
                    "schema_version": "herdr-control-state/v2",
                    "contract_id": "contract-a",
                    "controller_scope": scope,
                    "revision": 0,
                    "lanes": lanes,
                }
            ),
            encoding="utf-8",
        )

    def test_renames_before_publishing_verified_live_identity(self):
        client = FakeHerdr(
            [
                {
                    "name": "p2_worker_ready",
                    "pane_id": "w1:p2",
                    "agent_session": {"value": "session-p2"},
                }
            ]
        )

        result = assign_lane_name(self.path, "auth-api", client)

        self.assertEqual(client.calls, [("rename", "w1:p2", "p2_impl_auth")])
        self.assertEqual(result["agent_name"], "p2_impl_auth")
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(
            saved["lanes"]["auth-api"]["expected_agent_name"],
            "p2_impl_auth",
        )
        self.assertEqual(
            saved["lanes"]["auth-api"]["dispatch_agent_name"],
            "p2_impl_auth",
        )
        self.assertNotIn("name_assignment", saved["lanes"]["auth-api"])

    def test_stale_generation_fails_without_publishing(self):
        client = FakeHerdr(
            [
                {
                    "name": "p2_worker_ready",
                    "pane_id": "w1:p2",
                    "agent_session": {"value": "session-p2"},
                }
            ]
        )

        with self.assertRaisesRegex(AssignmentError, "generation"):
            assign_lane_name(
                self.path,
                "auth-api",
                client,
                expected_generation=2,
            )

    def test_generation_change_is_rejected_while_rename_is_reserved(self):
        errors = []

        def concurrent_generation_change():
            try:
                set_lane(
                    self.path,
                    "auth-api",
                    2,
                    "READY",
                    "receipt-g2.json",
                    {},
                )
            except SchedulerStateError as error:
                errors.append(str(error))

        client = FakeHerdr(
            [
                {
                    "name": "p2_worker_ready",
                    "pane_id": "w1:p2",
                    "agent_session": {"value": "session-p2"},
                }
            ],
            on_rename=concurrent_generation_change,
        )

        result = assign_lane_name(self.path, "auth-api", client)

        self.assertEqual(result["generation"], 1)
        self.assertEqual(errors, ["lane has a pending name assignment"])

    def test_session_disappears_clears_reservation_without_publishing(self):
        def drop_session(client):
            client.agents = []

        client = FakeHerdr(
            [
                {
                    "name": "p2_worker_ready",
                    "pane_id": "w1:p2",
                    "agent_session": {"value": "session-p2"},
                }
            ],
            after_rename=drop_session,
        )

        with self.assertRaisesRegex(AssignmentError, "verified"):
            assign_lane_name(self.path, "auth-api", client)

        saved = json.loads(self.path.read_text(encoding="utf-8"))
        lane = saved["lanes"]["auth-api"]
        self.assertEqual(lane["agent_name"], "p2_worker_ready")
        self.assertNotIn("name_assignment", lane)

    def test_migrates_working_p5_to_p9_without_changing_dispatch_receipts(self):
        definitions = [
            ("P5", "integration-owner", "integration_owner", None),
            ("P6", "integration-reviewer", "integration_review", None),
            ("P7", "qc", "qc", "rbac"),
            ("P8", "designer", "ui_review", None),
            ("P9", "persona", "persona", "admin"),
        ]
        lanes = {}
        agents = []
        for slot, role, display_role, display_slug in definitions:
            number = slot[1:]
            lane_id = f"lane-{number}"
            lanes[lane_id] = {
                "lane_id": lane_id,
                "generation": 1,
                "slot": slot,
                "role": role,
                "display_role": display_role,
                "display_slug": display_slug,
                "agent_name": f"hdr_p{number}",
                "dispatch_agent_name": f"hdr_p{number}",
                "pane_id": f"w1:p{number}",
                "session_id": f"session-p{number}",
                "input_identity": {},
                "receipt_path": str(self.root / f"{lane_id}.json"),
            }
            agents.append(
                {
                    "name": f"hdr_p{number}",
                    "pane_id": f"w1:p{number}",
                    "agent_status": "working",
                    "agent_session": {"value": f"session-p{number}"},
                }
            )
        self.write_state("scope-a", lanes)
        client = FakeHerdr(agents)

        result = migrate_legacy_lane_names(self.path, client)

        self.assertEqual(
            [item["agent_name"] for item in result],
            [
                "p5_integration_owner",
                "p6_integration_review",
                "p7_qc_rbac",
                "p8_ui_review",
                "p9_persona_admin",
            ],
        )
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["lanes"]["lane-7"]["dispatch_agent_name"], "hdr_p7")

    def test_other_controller_scope_cannot_reserve_same_session(self):
        other = self.root / "other-state.json"
        lane_b = dict(self.lane)
        lane_b["lane_id"] = "auth-review"
        lane_b["role"] = "integration-reviewer"
        lane_b["display_role"] = "integration_review"
        lane_b["display_slug"] = None
        self.write_state("scope-b", {"auth-review": lane_b}, path=other)
        client = FakeHerdr(
            [
                {
                    "name": "p2_worker_ready",
                    "pane_id": "w1:p2",
                    "agent_session": {"value": "session-p2"},
                }
            ]
        )
        registry = RuntimeRegistry(self.root, "sock-a")

        assign_lane_name(self.path, "auth-api", client, registry=registry)
        with self.assertRaisesRegex(AssignmentError, "session leased to another controller scope"):
            assign_lane_name(other, "auth-review", client, registry=registry)

        saved = json.loads(other.read_text(encoding="utf-8"))
        self.assertEqual(saved["lanes"]["auth-review"]["agent_name"], "p2_worker_ready")


if __name__ == "__main__":
    unittest.main()
