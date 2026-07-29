import tempfile
import threading
import unittest
from pathlib import Path

from scripts.runtime_registry import RegistryError, RuntimeRegistry


class RuntimeRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.registry = RuntimeRegistry(self.root, "sock-a")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_concurrent_reservations_allocate_distinct_names(self):
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def reserve(scope, slot):
            try:
                barrier.wait()
                results.append(
                    self.registry.reserve_visible_name(
                        controller_scope=scope,
                        slot=slot,
                        role="impl",
                        task="auth",
                        reservation_token=f"{scope}-token",
                    )["name"]
                )
            except Exception as exc:  # pragma: no cover - preserves thread failure
                errors.append(exc)

        threads = [
            threading.Thread(target=reserve, args=("scope-a", "P2")),
            threading.Thread(target=reserve, args=("scope-b", "P2")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(len(set(results)), 2)

    def test_live_herdr_names_are_treated_as_occupied(self):
        result = self.registry.reserve_visible_name(
            controller_scope="scope-a",
            slot="P1",
            role="orchestrator",
            reservation_token="token-a",
            live_names={"p1_orchestrator"},
        )

        self.assertNotEqual(result["name"], "p1_orchestrator")

    def test_finalized_scope_keeps_stable_name_after_other_name_is_freed(self):
        first = self.registry.reserve_visible_name(
            controller_scope="scope-a",
            slot="P2",
            role="impl",
            task="auth",
            reservation_token="token-a",
        )
        self.registry.finalize_visible_name(
            controller_scope="scope-a",
            reservation_token="token-a",
            session_id="session-a",
            name=first["name"],
        )
        second = self.registry.reserve_visible_name(
            controller_scope="scope-b",
            slot="P2",
            role="impl",
            task="auth",
            reservation_token="token-b",
        )
        self.registry.release_visible_name(
            controller_scope="scope-b",
            session_id="session-b",
            name=second["name"],
        )

        resumed = self.registry.reserve_visible_name(
            controller_scope="scope-a",
            slot="P2",
            role="impl",
            task="schema",
            reservation_token="token-a2",
        )

        self.assertEqual(resumed["name"], first["name"])

    def test_live_session_is_leased_to_one_scope_lane(self):
        self.registry.lease_session(
            session_id="session-a",
            controller_scope="scope-a",
            contract_id="contract-a",
            lane_id="lane-a",
            generation="g1",
        )

        with self.assertRaisesRegex(RegistryError, "already leased"):
            self.registry.lease_session(
                session_id="session-a",
                controller_scope="scope-b",
                contract_id="contract-a",
                lane_id="lane-b",
                generation="g1",
            )

    def test_finalized_session_can_record_lane_metadata_later(self):
        reservation = self.registry.reserve_visible_name(
            controller_scope="scope-a",
            slot="P2",
            role="impl",
            task="auth",
            reservation_token="token-a",
        )
        self.registry.finalize_visible_name(
            controller_scope="scope-a",
            reservation_token="token-a",
            session_id="session-a",
            name=reservation["name"],
        )

        lease = self.registry.lease_session(
            session_id="session-a",
            controller_scope="scope-a",
            contract_id="contract-a",
            lane_id="lane-a",
            generation="g1",
        )

        self.assertEqual(lease["contract_id"], "contract-a")
        self.assertEqual(lease["lane_id"], "lane-a")
        self.assertEqual(lease["generation"], "g1")

    def test_same_token_resumes_pending_reservation_after_interruption(self):
        first = self.registry.reserve_visible_name(
            controller_scope="scope-a",
            slot="P3",
            role="worker",
            task="ready",
            reservation_token="token-a",
        )
        resumed = self.registry.reserve_visible_name(
            controller_scope="scope-a",
            slot="P3",
            role="worker",
            task="ready",
            reservation_token="token-a",
        )

        self.assertEqual(resumed, first)

    def test_different_token_cannot_steal_pending_reservation(self):
        self.registry.reserve_visible_name(
            controller_scope="scope-a",
            slot="P3",
            role="worker",
            task="ready",
            reservation_token="token-a",
        )

        with self.assertRaisesRegex(RegistryError, "pending reservation"):
            self.registry.reserve_visible_name(
                controller_scope="scope-a",
                slot="P3",
                role="worker",
                task="ready",
                reservation_token="token-b",
            )

    def test_only_recorded_legacy_session_claims_global_resources(self):
        claimed = self.registry.claim_legacy_resources(
            controller_scope="scope-a",
            session_id="legacy-p1",
        )

        self.assertEqual(claimed["controller_scope"], "scope-a")
        self.assertEqual(claimed["session_id"], "legacy-p1")
        with self.assertRaisesRegex(RegistryError, "legacy resources"):
            self.registry.claim_legacy_resources(
                controller_scope="scope-b",
                session_id="legacy-p2",
            )


if __name__ == "__main__":
    unittest.main()
