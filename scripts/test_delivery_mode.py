import unittest

from scripts.delivery_mode import required_mode, validate_mode


def compact_risk():
    return {
        "local": True,
        "low_risk": True,
        "path_owned": True,
        "deterministic_acceptance": True,
    }


class DeliveryModeTests(unittest.TestCase):
    def test_one_deterministic_local_lane_is_compact(self):
        risk = compact_risk()

        self.assertEqual(required_mode(risk), "Compact")
        validate_mode(
            "Compact",
            risk,
            {"P7": False, "P8": False, "P9": False},
            1,
        )

    def test_compact_accepts_one_to_three_implementation_lanes(self):
        for lane_count in (1, 2, 3):
            with self.subTest(lane_count=lane_count):
                validate_mode(
                    "Compact",
                    compact_risk(),
                    {"P7": False, "P8": False, "P9": False},
                    lane_count,
                )

    def test_each_risk_trigger_requires_standard(self):
        triggers = {
            "not_local": ("local", False),
            "not_low_risk": ("low_risk", False),
            "not_path_owned": ("path_owned", False),
            "no_deterministic_acceptance": ("deterministic_acceptance", False),
            "browser_or_visual": ("browser_or_visual", True),
            "auth_rbac_security_privacy_or_secrets": (
                "auth_rbac_security_privacy_or_secrets",
                True,
            ),
            "schema_migration_or_destructive": (
                "schema_migration_or_destructive",
                True,
            ),
            "deployment_or_external_state": (
                "deployment_or_external_state",
                True,
            ),
            "nondeterministic_acceptance": ("nondeterministic_acceptance", True),
            "high_assurance": ("high_assurance", True),
            "broader_review": ("broader_review", True),
            "runtime_recovery": ("runtime_recovery", True),
        }
        for trigger, (field, value) in triggers.items():
            with self.subTest(trigger=trigger):
                risk = compact_risk()
                risk[field] = value
                self.assertEqual(required_mode(risk), "Standard")
                with self.assertRaisesRegex(ValueError, "requires Standard"):
                    validate_mode(
                        "Compact",
                        risk,
                        {"P7": False, "P8": False, "P9": False},
                        1,
                    )

    def test_more_than_three_lanes_requires_standard(self):
        with self.assertRaisesRegex(ValueError, "requires Standard"):
            validate_mode(
                "Compact",
                compact_risk(),
                {"P7": False, "P8": False, "P9": False},
                4,
            )

        validate_mode(
            "Standard",
            compact_risk(),
            {"P7": True, "P8": False, "P9": True},
            4,
        )

    def test_unknown_risk_flags_fail(self):
        risk = compact_risk()
        risk["surprise"] = False

        with self.assertRaisesRegex(ValueError, "unknown risk flags: surprise"):
            required_mode(risk)

    def test_missing_compact_eligibility_requires_standard(self):
        risk = compact_risk()
        del risk["local"]

        self.assertEqual(required_mode(risk), "Standard")

    def test_current_high_assurance_manifest_risk_is_standard(self):
        risk = {
            "deterministic_acceptance": True,
            "high_assurance": True,
            "runtime_recovery": True,
        }

        self.assertEqual(required_mode(risk), "Standard")
        validate_mode(
            "Standard",
            risk,
            {"P7": True, "P8": False, "P9": True},
            3,
        )

    def test_unknown_mode_fails(self):
        with self.assertRaisesRegex(ValueError, "mode must be Compact or Standard"):
            validate_mode(
                "Automatic",
                compact_risk(),
                {"P7": False, "P8": False, "P9": False},
                1,
            )

    def test_compact_with_applicable_p7_to_p9_review_fails(self):
        for slot in ("P7", "P8", "P9"):
            with self.subTest(slot=slot):
                applicability = {"P7": False, "P8": False, "P9": False}
                applicability[slot] = True
                with self.assertRaisesRegex(
                    ValueError, "Compact cannot require P7, P8, or P9"
                ):
                    validate_mode("Compact", compact_risk(), applicability, 1)

    def test_review_applicability_requires_exact_boolean_slots(self):
        with self.assertRaisesRegex(ValueError, "unknown review slots: P10"):
            validate_mode(
                "Compact",
                compact_risk(),
                {"P7": False, "P8": False, "P9": False, "P10": False},
                1,
            )
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            validate_mode(
                "Compact",
                compact_risk(),
                {"P7": False, "P8": False, "P9": "no"},
                1,
            )


if __name__ == "__main__":
    unittest.main()
