import json
import importlib.util
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

    def test_runner_rejects_less_than_three_trials(self):
        with self.assertRaisesRegex(ValueError, "at least 3"):
            benchmark.run_trials(trials=2)


if __name__ == "__main__":
    unittest.main()
