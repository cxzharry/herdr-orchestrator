import json
import importlib.util
import hashlib
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("run_benchmark.py")
spec = importlib.util.spec_from_file_location("persistent_p1_benchmark", MODULE_PATH)
benchmark = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(benchmark)


class PersistentP1BenchmarkTests(unittest.TestCase):
    def test_scenario_covers_active_disjoint_overlap_and_plan_required_deltas(self):
        result = benchmark.simulate_scenario()

        self.assertEqual(result["active_lanes"], ["P2", "P3"])
        self.assertEqual(result["deltas"]["disjoint"]["state"], "ACTIVE")
        self.assertEqual(result["deltas"]["disjoint"]["assigned_lane"], "P4")
        self.assertEqual(result["deltas"]["overlap"]["state"], "DEPENDENCY_BLOCKED")
        self.assertEqual(result["deltas"]["plan_required"]["state"], "PLAN_REQUIRED")

    def test_runner_records_median_and_p95_for_three_or_more_trials(self):
        with tempfile.TemporaryDirectory() as dirname:
            output_path = Path(dirname) / "summary.json"
            summary = benchmark.run_trials(trials=3, output_path=output_path)

            self.assertTrue(output_path.is_file())
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(summary, payload)
            self.assertEqual(payload["trials"], 3)
            for metric in (
                "scheduler_tick_ms",
                "disjoint_dispatch_ms",
                "overlap_queue_ms",
                "capacity_blocked_ms",
                "scenario_wall_ms",
            ):
                self.assertIn("median", payload["metrics"][metric])
                self.assertIn("p95", payload["metrics"][metric])
            rendered = json.dumps(payload)
            self.assertNotIn(str(Path.home()), rendered)
            self.assertNotIn("/tmp/", rendered)

    def test_runner_records_raw_samples_from_real_transition_measurements(self):
        summary = benchmark.run_trials(trials=3)

        self.assertEqual(len(summary["raw_samples"]), 3)
        for sample in summary["raw_samples"]:
            self.assertEqual(sample["transitions"]["disjoint"], "P4")
            self.assertEqual(sample["transitions"]["overlap"], "P3")
            self.assertEqual(sample["transitions"]["capacity"], "CAPACITY_BLOCKED")
            for metric, value in sample["timings_ms"].items():
                self.assertGreater(value, 0, metric)
                self.assertNotIn(value, {0.01, 1.0}, metric)

    def test_baseline_report_input_validates_digest_and_records_fair_comparison(self):
        with tempfile.TemporaryDirectory() as dirname:
            baseline_path = Path(dirname) / "baseline.json"
            baseline = {
                "schema_version": "herdr-clean-baseline-report/v1",
                "raw_evidence": {
                    "blocking_wait_probe": {
                        "elapsed_seconds": 0.123,
                        "exit_code": 0,
                        "status": "timed_out_waiting",
                    }
                },
                "comparison": {"superpowers": "N/A"},
            }
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            digest = hashlib.sha256(baseline_path.read_bytes()).hexdigest()

            summary = benchmark.run_trials(
                trials=3,
                baseline_report=baseline_path,
                baseline_sha256=digest,
            )

            comparison = summary["comparison"]
            self.assertEqual(comparison["primary_baseline"]["sha256"], digest)
            self.assertEqual(
                comparison["primary_baseline"]["old_blocking_wait_ms"],
                123.0,
            )
            self.assertIn("revised_tick_ms", comparison["primary_baseline"])
            self.assertEqual(comparison["superpowers"], "N/A")
            self.assertNotIn("universal", json.dumps(comparison).lower())

    def test_baseline_report_digest_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as dirname:
            baseline_path = Path(dirname) / "baseline.json"
            baseline_path.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "sha256"):
                benchmark.run_trials(
                    trials=3,
                    baseline_report=baseline_path,
                    baseline_sha256="0" * 64,
                )

    def test_runner_rejects_less_than_three_trials(self):
        with self.assertRaisesRegex(ValueError, "at least 3"):
            benchmark.run_trials(trials=2)


if __name__ == "__main__":
    unittest.main()
