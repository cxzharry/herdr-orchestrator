import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_performance import (
    PerformanceError,
    load_frozen_baseline,
    validate_candidate,
)


class PerformanceTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
