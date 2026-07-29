import unittest

from scripts.agent_naming import (
    NamingError,
    canonical_display_role,
    format_agent_name,
    slot_from_agent_name,
    slot_from_lane_id,
    stable_agent_identity,
)


class AgentNamingTests(unittest.TestCase):
    def test_parses_legacy_and_dynamic_names_to_the_same_slot(self):
        self.assertEqual(slot_from_agent_name("hdr_p2"), "P2")
        self.assertEqual(slot_from_agent_name("p2_worker_ready"), "P2")
        self.assertEqual(slot_from_agent_name("p2_impl_auth"), "P2")

    def test_formats_role_and_task_as_a_bounded_herdr_name(self):
        value = format_agent_name(
            "P8",
            "UI Review",
            "Checkout accessibility and responsive behavior",
        )
        self.assertTrue(value.startswith("p8_ui_review_"))
        self.assertLessEqual(len(value), 32)
        self.assertRegex(value, r"^[a-z][a-z0-9_-]{0,31}$")

    def test_formats_controller_and_ready_workers(self):
        self.assertEqual(
            format_agent_name("P1", "orchestrator"),
            "p1_orchestrator",
        )
        self.assertEqual(
            format_agent_name("P3", "worker", "ready"),
            "p3_worker_ready",
        )
        self.assertEqual(
            format_agent_name("P5", "integration_owner"),
            "p5_integration_owner",
        )
        self.assertEqual(
            format_agent_name("P6", "integration_review"),
            "p6_integration_review",
        )

    def test_collision_suffix_is_deterministic(self):
        occupied = {"p2_impl_auth"}
        first = format_agent_name(
            "P2",
            "impl",
            "auth",
            occupied=occupied,
            collision_key="lane-auth",
        )
        second = format_agent_name(
            "P2",
            "impl",
            "auth",
            occupied=occupied,
            collision_key="lane-auth",
        )
        self.assertEqual(first, second)
        self.assertNotEqual(first, "p2_impl_auth")
        self.assertLessEqual(len(first), 32)

    def test_collision_without_lane_identity_fails_closed(self):
        with self.assertRaisesRegex(NamingError, "collision_key"):
            format_agent_name(
                "P2",
                "impl",
                "auth",
                occupied={"p2_impl_auth"},
            )

    def test_collision_suffix_extends_until_the_name_is_unique(self):
        first = format_agent_name(
            "P2",
            "impl",
            "auth",
            occupied={"p2_impl_auth"},
            collision_key="lane-auth",
        )
        second = format_agent_name(
            "P2",
            "impl",
            "auth",
            occupied={"p2_impl_auth", first},
            collision_key="lane-auth",
        )
        self.assertNotEqual(first, second)
        self.assertLessEqual(len(second), 32)

    def test_long_task_truncates_only_the_task_segment(self):
        value = format_agent_name(
            "P9",
            "persona",
            "administrator_checkout_approval_journey",
        )
        self.assertTrue(value.startswith("p9_persona_"))
        self.assertLessEqual(len(value), 32)

    def test_derives_only_canonical_legacy_metadata(self):
        self.assertEqual(slot_from_lane_id("p8"), "P8")
        self.assertIsNone(slot_from_lane_id("checkout-ui"))
        self.assertEqual(
            canonical_display_role("P5", "integration-owner"),
            "integration_owner",
        )
        self.assertEqual(
            canonical_display_role("P8", "designer"),
            "ui_review",
        )

    def test_request_identity_uses_slot_and_session_not_display_name(self):
        first = stable_agent_identity("p2_impl_auth", "session-p2")
        renamed = stable_agent_identity("p2_impl_schema", "session-p2")
        legacy = stable_agent_identity("hdr_p2", "session-p2")
        self.assertEqual(first, renamed)
        self.assertEqual(first, legacy)


if __name__ == "__main__":
    unittest.main()
