import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_performance import (
    PerformanceError,
    load_candidate,
    load_frozen_baseline,
    load_previous_glob,
    validate_candidate,
    verify_baseline_file,
)


def compact_identity():
    return {
        "base_sha": "9f5ece92b836d240a95463949e503b0dab366631",
        "acceptance_command": ["python3", "verify.py"],
    }


def multi_module_identity():
    return {
        "base_sha": "405cf96fd675c607768dafec8ede1aeae5725359",
        "acceptance_command": [
            "python3", "-B", "-m", "unittest", "discover", "-s", "tests", "-v",
        ],
        "deep_immutability_command": [
            "python3", "-B", "-m", "unittest",
            "tests.test_canary_integration.CanaryIntegrationTests."
            "test_policy_constructor_deep_freezes_nested_inputs",
            "-v",
        ],
    }


COMPACT_MANIFEST_SHA256 = "03ac319ef4b73602fda26c4a7cb02bc46eacfb61d002305b38cdad396c3c7708"
MULTI_MODULE_MANIFEST_SHA256 = "5de918d0db65c327e471317cc6ec796429d6fad8e3c03693775a5765cdb99667"


class PerformanceTest(unittest.TestCase):
    def test_verify_baseline_file_preserves_frozen_digest(self):
        self.assertEqual(
            "35cd49358231e12d435be11d1b1200472ba27a76784530346a9bf743994cf12b",
            verify_baseline_file(Path("benchmarks/frozen-superpowers-v1.json")),
        )

    def test_frozen_values_and_source_digests(self):
        baseline = load_frozen_baseline(
            Path("benchmarks/frozen-superpowers-v1.json")
        )
        self.assertEqual(152, baseline["compact"]["seconds"])
        self.assertEqual(1009, baseline["multi_module"]["seconds"])

    def test_rejects_candidate_that_only_matches_baseline(self):
        baseline = {
            "compact": {"seconds": 152},
            "multi_module": {"seconds": 1009},
        }
        with self.assertRaisesRegex(PerformanceError, "compact"):
            validate_candidate(
                baseline,
                {
                    "compact": {"seconds": 152, "verified": True},
                    "multi_module": {
                        "seconds": 900,
                        "verified": True,
                        "deep_immutability": True,
                    },
                },
                [],
            )

    def test_warns_when_slower_than_best_herdr(self):
        result = validate_candidate(
            {
                "compact": {"seconds": 152},
                "multi_module": {"seconds": 1009},
            },
            {
                "compact": {"seconds": 120, "verified": True},
                "multi_module": {
                    "seconds": 900,
                    "verified": True,
                    "deep_immutability": True,
                },
            },
            [{"compact": {"seconds": 100}, "multi_module": {"seconds": 800}}],
        )
        self.assertEqual(
            ["compact >10% slower than best Herdr",
             "multi_module >10% slower than best Herdr"],
            result["warnings"],
        )

    def test_does_not_warn_at_ten_percent_boundary(self):
        result = validate_candidate(
            {
                "compact": {"seconds": 152},
                "multi_module": {"seconds": 1009},
            },
            {
                "compact": {"seconds": 110,
                            "verified": True},
                "multi_module": {
                    "seconds": 880,
                    "verified": True,
                    "deep_immutability": True,
                },
            },
            [{"compact": {"seconds": 100}, "multi_module": {"seconds": 800}}],
        )
        self.assertEqual([], result["warnings"])

    def test_validates_sha_addressed_candidate_and_previous_glob(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate_path = root / "abc123.json"
            previous_path = root / "previous-001.json"
            candidate_path.write_text(
                json.dumps(
                    {
                        "schema_version": "herdr-performance-candidate/v1",
                        "candidate_sha": "abc123",
                        "previous_candidate_sha": "previous-001",
                        "baseline_sha256": verify_baseline_file(
                            Path("benchmarks/frozen-superpowers-v1.json")
                        ),
                        "scenarios": {
                            "compact": {
                                "scenario_id": "compact-control-plane-v1",
                                "manifest_sha256": COMPACT_MANIFEST_SHA256,
                                "seconds": 111,
                                "verified": True,
                                "scope_clean": True,
                                "scenario_identity": compact_identity(),
                                "rework_loops": 0,
                                "raw_evidence": ["control-plane transcript"],
                            },
                            "multi_module": {
                                "scenario_id": "multi-module-canary-v1",
                                "manifest_sha256": MULTI_MODULE_MANIFEST_SHA256,
                                "seconds": 840,
                                "verified": True,
                                "scope_clean": True,
                                "deep_immutability": True,
                                "scenario_identity": multi_module_identity(),
                                "rework_loops": 2,
                                "raw_evidence": ["canary receipt"],
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            previous_path.write_text(
                json.dumps(
                    {
                        "schema_version": "herdr-performance-candidate/v1",
                        "candidate_sha": "previous-001",
                        "scenarios": {
                            "compact": {"seconds": 100},
                            "multi_module": {"seconds": 800},
                        },
                    }
                ),
                encoding="utf-8",
            )

            candidate = load_candidate(candidate_path)
            result = validate_candidate(
                load_frozen_baseline(Path("benchmarks/frozen-superpowers-v1.json")),
                candidate,
                load_previous_glob(str(root / "*.json"), candidate_path),
            )

        self.assertEqual(["compact >10% slower than best Herdr"], result["warnings"])

    def test_rejects_missing_immediately_preceding_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate_path = root / "abc123.json"
            candidate_path.write_text(
                json.dumps(
                    {
                        "schema_version": "herdr-performance-candidate/v1",
                        "candidate_sha": "abc123",
                        "previous_candidate_sha": "missing",
                        "baseline_sha256": verify_baseline_file(
                            Path("benchmarks/frozen-superpowers-v1.json")
                        ),
                        "scenarios": {
                            "compact": {
                                "scenario_id": "compact-control-plane-v1",
                                "manifest_sha256": COMPACT_MANIFEST_SHA256,
                                "seconds": 111,
                                "verified": True,
                                "scope_clean": True,
                                "scenario_identity": compact_identity(),
                                "rework_loops": 0,
                                "raw_evidence": ["control-plane transcript"],
                            },
                            "multi_module": {
                                "scenario_id": "multi-module-canary-v1",
                                "manifest_sha256": MULTI_MODULE_MANIFEST_SHA256,
                                "seconds": 840,
                                "verified": True,
                                "scope_clean": True,
                                "deep_immutability": True,
                                "scenario_identity": multi_module_identity(),
                                "rework_loops": 2,
                                "raw_evidence": ["canary receipt"],
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(PerformanceError, "immediately preceding"):
                validate_candidate(
                    load_frozen_baseline(Path("benchmarks/frozen-superpowers-v1.json")),
                    load_candidate(candidate_path),
                    load_previous_glob(str(root / "*.json"), candidate_path),
                )

    def test_rejects_unmeasured_or_unverified_candidate(self):
        baseline = {
            "compact": {"seconds": 152},
            "multi_module": {"seconds": 1009},
        }
        with self.assertRaisesRegex(PerformanceError, "integer seconds"):
            validate_candidate(
                baseline,
                {
                    "candidate_sha": "abc123",
                    "baseline_sha256": verify_baseline_file(
                        Path("benchmarks/frozen-superpowers-v1.json")
                    ),
                    "scenarios": {
                        "compact": {
                            "scenario_id": "compact-control-plane-v1",
                            "manifest_sha256": COMPACT_MANIFEST_SHA256,
                            "seconds": 111.5,
                            "verified": True,
                            "scope_clean": True,
                            "scenario_identity": compact_identity(),
                            "rework_loops": 0,
                            "raw_evidence": ["control-plane transcript"],
                        },
                        "multi_module": {
                            "scenario_id": "multi-module-canary-v1",
                            "manifest_sha256": MULTI_MODULE_MANIFEST_SHA256,
                            "seconds": 840,
                            "verified": True,
                            "scope_clean": True,
                            "deep_immutability": True,
                            "scenario_identity": multi_module_identity(),
                            "rework_loops": 2,
                            "raw_evidence": ["canary receipt"],
                        },
                    },
                },
                [],
            )

    def test_freezes_executable_scenario_manifests(self):
        for path in (
            Path("benchmarks/scenarios/compact-control-plane-v1.json"),
            Path("benchmarks/scenarios/multi-module-canary-v1.json"),
        ):
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("herdr-benchmark-scenario/v1", value["schema_version"])
            self.assertTrue(value["base_sha"])
            self.assertTrue(value["base_snapshot"])
            self.assertNotIn("final-herdr-cf3abac", value["base_snapshot"])
            self.assertTrue(value["isolation_copy_procedure"])
            self.assertTrue(value["task_input"])
            self.assertTrue(value["acceptance_command"])
            self.assertTrue(value["source_artifacts"])

    def test_rejects_verification_only_candidate_identity(self):
        baseline = {
            "compact": {"seconds": 152},
            "multi_module": {"seconds": 1009},
        }
        with self.assertRaisesRegex(PerformanceError, "manifest digest"):
            validate_candidate(
                baseline,
                {
                    "candidate_sha": "abc123",
                    "baseline_sha256": verify_baseline_file(
                        Path("benchmarks/frozen-superpowers-v1.json")
                    ),
                    "scenarios": {
                        "compact": {
                            "scenario_id": "compact-control-plane-v1",
                            "manifest_sha256": "changed",
                            "seconds": 111,
                            "verified": True,
                            "scope_clean": True,
                            "scenario_identity": compact_identity(),
                            "rework_loops": 0,
                            "raw_evidence": ["acceptance after output exists"],
                        },
                        "multi_module": {
                            "scenario_id": "multi-module-canary-v1",
                            "manifest_sha256": MULTI_MODULE_MANIFEST_SHA256,
                            "seconds": 840,
                            "verified": True,
                            "scope_clean": True,
                            "deep_immutability": True,
                            "scenario_identity": multi_module_identity(),
                            "rework_loops": 2,
                            "raw_evidence": ["acceptance after output exists"],
                        },
                    },
                },
                [],
            )


if __name__ == "__main__":
    unittest.main()
