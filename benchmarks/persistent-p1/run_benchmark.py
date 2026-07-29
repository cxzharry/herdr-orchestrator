#!/usr/bin/env python3
"""Deterministic persistent-P1 scenario benchmark harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Any


SCENARIO_PATH = Path(__file__).with_name("scenario.json")


def _scenario() -> dict[str, Any]:
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))


def _classify_delta(
    delta: dict[str, Any],
    active: dict[str, set[str]],
    idle: list[str],
) -> dict[str, Any]:
    if delta.get("risk") in {"architecture", "public_contract", "security", "schema"}:
        return {"state": "PLAN_REQUIRED"}
    paths = set(delta.get("affected_paths") or [])
    for lane, owned in active.items():
        if paths & owned:
            return {"state": "DEPENDENCY_BLOCKED", "dependency": lane}
    if not idle:
        return {"state": "CAPACITY_BLOCKED"}
    lane = idle.pop(0)
    active[lane] = paths
    return {"state": "ACTIVE", "assigned_lane": lane}


def simulate_scenario() -> dict[str, Any]:
    scenario = _scenario()
    active = {
        item["lane"]: set(item["owned_paths"])
        for item in scenario["active_lanes"]
    }
    idle = ["P4"]
    deltas: dict[str, dict[str, Any]] = {}
    for delta in scenario["deltas"]:
        deltas[delta["delta_id"]] = _classify_delta(delta, active, idle)
    return {
        "active_lanes": [item["lane"] for item in scenario["active_lanes"]],
        "deltas": deltas,
    }


def _initial_state() -> tuple[dict[str, set[str]], list[str]]:
    scenario = _scenario()
    active = {
        item["lane"]: set(item["owned_paths"])
        for item in scenario["active_lanes"]
    }
    return active, ["P4"]


def _percentile95(values: list[float]) -> float:
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
    return ordered[index]


def _summarize(values: list[float]) -> dict[str, float]:
    return {
        "median": round(statistics.median(values), 6),
        "p95": round(_percentile95(values), 6),
    }


def _elapsed_ms(start_ns: int) -> float:
    return max((time.perf_counter_ns() - start_ns) / 1_000_000, 0.000001)


def _measured_transition(
    delta: dict[str, Any],
    active: dict[str, set[str]],
    idle: list[str],
) -> tuple[dict[str, Any], float]:
    start_ns = time.perf_counter_ns()
    result = _classify_delta(delta, active, idle)
    return result, _elapsed_ms(start_ns)


def _trial() -> dict[str, Any]:
    scenario = _scenario()
    active, idle = _initial_state()
    timings: dict[str, float] = {}
    transitions: dict[str, str] = {}
    deltas: dict[str, dict[str, Any]] = {}
    scenario_start_ns = time.perf_counter_ns()
    tick_start_ns = time.perf_counter_ns()

    for delta in scenario["deltas"]:
        result, elapsed = _measured_transition(delta, active, idle)
        delta_id = delta["delta_id"]
        deltas[delta_id] = result
        if delta_id == "disjoint":
            timings["disjoint_dispatch_ms"] = elapsed
            transitions[delta_id] = result["assigned_lane"]
        elif delta_id == "overlap":
            timings["overlap_queue_ms"] = elapsed
            transitions[delta_id] = result["dependency"]
        elif delta_id == "capacity":
            timings["capacity_blocked_ms"] = elapsed
            transitions[delta_id] = result["state"]
        elif delta_id == "plan_required":
            transitions[delta_id] = result["state"]

    timings["scheduler_tick_ms"] = _elapsed_ms(tick_start_ns)
    timings["scenario_wall_ms"] = _elapsed_ms(scenario_start_ns)
    return {"timings_ms": timings, "transitions": transitions, "deltas": deltas}


def _validate_baseline(path: Path, expected_sha256: str) -> dict[str, Any]:
    payload = path.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected_sha256:
        raise ValueError("baseline report sha256 mismatch")
    report = json.loads(payload)
    if report.get("schema_version") != "herdr-clean-baseline-report/v1":
        raise ValueError("unsupported baseline report schema")
    probe = (report.get("raw_evidence") or {}).get("blocking_wait_probe")
    if not isinstance(probe, dict) or "elapsed_seconds" not in probe:
        raise ValueError("baseline report lacks blocking_wait_probe elapsed_seconds")
    return report


def _comparison(
    report: dict[str, Any],
    digest: str,
    metrics: dict[str, dict[str, float]],
) -> dict[str, Any]:
    probe = report["raw_evidence"]["blocking_wait_probe"]
    superpowers = (
        (report.get("benchmark_facts") or {})
        .get("superpowers_current_locked_inputs", {})
        .get("status", "N/A")
    )
    return {
        "primary_baseline": {
            "schema_version": report["schema_version"],
            "sha256": digest,
            "old_blocking_wait_ms": round(float(probe["elapsed_seconds"]) * 1000, 6),
            "old_blocking_wait_status": probe.get("status"),
            "revised_tick_ms": metrics["scheduler_tick_ms"],
        },
        "superpowers": superpowers,
        "claim_scope": "scenario-specific baseline comparison only",
    }


def run_trials(
    trials: int = 3,
    output_path: Path | None = None,
    baseline_report: Path | None = None,
    baseline_sha256: str | None = None,
) -> dict[str, Any]:
    if trials < 3:
        raise ValueError("benchmark requires at least 3 trials")
    raw = [_trial() for _ in range(trials)]
    metrics = {
        metric: _summarize([trial["timings_ms"][metric] for trial in raw])
        for metric in raw[0]["timings_ms"]
    }
    summary = {
        "schema_version": "herdr-persistent-p1-benchmark/v1",
        "scenario": _scenario()["name"],
        "trials": trials,
        "raw_samples": raw,
        "metrics": metrics,
        "result": simulate_scenario(),
        "methodology": "standard-library deterministic scheduler simulation",
    }
    if baseline_report or baseline_sha256:
        if not baseline_report or not baseline_sha256:
            raise ValueError("baseline report and sha256 must be provided together")
        report = _validate_baseline(baseline_report, baseline_sha256)
        summary["comparison"] = _comparison(report, baseline_sha256, metrics)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline-report", type=Path)
    parser.add_argument("--baseline-sha256")
    args = parser.parse_args()
    try:
        summary = run_trials(
            args.trials,
            args.output,
            baseline_report=args.baseline_report,
            baseline_sha256=args.baseline_sha256,
        )
    except ValueError as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
