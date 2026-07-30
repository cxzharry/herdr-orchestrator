#!/usr/bin/env python3
"""Validate replacement benchmark results against frozen baselines."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import subprocess
from pathlib import Path


class PerformanceError(RuntimeError):
    pass


FROZEN_BASELINE_SHA256 = "35cd49358231e12d435be11d1b1200472ba27a76784530346a9bf743994cf12b"
SCENARIO_IDS = {
    "compact": "compact-control-plane-v1",
    "multi_module": "multi-module-canary-v1",
}
SCENARIO_DIR = Path("benchmarks/scenarios")


def verify_baseline_file(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != FROZEN_BASELINE_SHA256:
        raise PerformanceError("frozen baseline digest mismatch")
    return digest


def load_frozen_baseline(path: Path) -> dict:
    verify_baseline_file(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "herdr-frozen-superpowers/v1":
        raise PerformanceError("unsupported frozen baseline")
    _verify_source_digest(path.parent.parent, value["compact"])
    _verify_source_digest(path.parent.parent, value["multi_module"])
    return value


def load_candidate(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "herdr-performance-candidate/v1":
        raise PerformanceError("unsupported candidate schema_version")
    candidate_sha = value.get("candidate_sha")
    if not candidate_sha:
        raise PerformanceError("candidate_sha is required")
    if path.stem != candidate_sha:
        raise PerformanceError("candidate filename must match candidate_sha")
    return value


def load_previous_glob(pattern: str, candidate_path: Path | None = None) -> list[dict]:
    previous = []
    candidate_resolved = candidate_path.resolve() if candidate_path else None
    for item in sorted(glob.glob(pattern)):
        path = Path(item)
        if candidate_resolved and path.resolve() == candidate_resolved:
            continue
        previous.append(json.loads(path.read_text(encoding="utf-8")))
    return previous


def validate_candidate(baseline: dict, candidate: dict, previous: list[dict]) -> dict:
    if "scenarios" in candidate:
        return _validate_candidate_v1(baseline, candidate, previous)

    failures = []
    if not candidate["compact"]["verified"]:
        failures.append("compact acceptance failed")
    if candidate["compact"]["seconds"] >= baseline["compact"]["seconds"]:
        failures.append("compact did not beat frozen baseline")
    multi = candidate["multi_module"]
    if not multi["verified"] or not multi["deep_immutability"]:
        failures.append("multi_module quality failed")
    if multi["seconds"] >= baseline["multi_module"]["seconds"]:
        failures.append("multi_module did not beat frozen baseline")
    if failures:
        raise PerformanceError("; ".join(failures))

    warnings = []
    for key in ("compact", "multi_module"):
        samples = [item[key]["seconds"] for item in previous if key in item]
        if samples and candidate[key]["seconds"] > min(samples) * 1.10:
            warnings.append(f"{key} >10% slower than best Herdr")
    return {"status": "pass", "warnings": warnings}


def _validate_candidate_v1(baseline: dict, candidate: dict, previous: list[dict]) -> dict:
    failures = []
    if candidate.get("baseline_sha256") != FROZEN_BASELINE_SHA256:
        failures.append("baseline digest does not match frozen baseline")

    previous_sha = candidate.get("previous_candidate_sha")
    previous_by_sha = {
        item.get("candidate_sha"): item
        for item in previous
        if item.get("candidate_sha")
    }
    if previous_sha and previous_sha not in previous_by_sha:
        failures.append("missing immediately preceding evidence")

    scenarios = candidate.get("scenarios", {})
    compact = _scenario(scenarios, "compact", failures)
    multi = _scenario(scenarios, "multi_module", failures)

    if compact and compact["seconds"] >= baseline["compact"]["seconds"]:
        failures.append("compact did not beat frozen baseline")
    if multi and multi["seconds"] >= baseline["multi_module"]["seconds"]:
        failures.append("multi_module did not beat frozen baseline")
    if failures:
        raise PerformanceError("; ".join(failures))

    warnings = []
    for key in ("compact", "multi_module"):
        samples = [
            item.get("scenarios", {}).get(key, item.get(key, {})).get("seconds")
            for item in previous
        ]
        samples = [seconds for seconds in samples if isinstance(seconds, int)]
        if samples and scenarios[key]["seconds"] > min(samples) * 1.10:
            warnings.append(f"{key} >10% slower than best Herdr")
    return {"status": "pass", "warnings": warnings}


def _scenario(scenarios: dict, key: str, failures: list[str]) -> dict | None:
    value = scenarios.get(key)
    if not isinstance(value, dict):
        failures.append(f"{key} scenario is required")
        return None
    if value.get("scenario_id") != SCENARIO_IDS[key]:
        failures.append(f"{key} scenario_id does not match manifest")
    if value.get("manifest_sha256") != _scenario_manifest_sha256(SCENARIO_IDS[key]):
        failures.append(f"{key} manifest digest does not match scenario manifest")
    expected_identity = _scenario_identity(SCENARIO_IDS[key])
    if value.get("scenario_identity") != expected_identity:
        failures.append(f"{key} scenario identity does not match manifest")
    if not isinstance(value.get("seconds"), int) or isinstance(value.get("seconds"), bool):
        failures.append(f"{key} requires measured integer seconds")
    if not value.get("verified"):
        failures.append(f"{key} acceptance failed")
    if not value.get("scope_clean"):
        failures.append(f"{key} scope was not clean")
    if key == "multi_module" and not value.get("deep_immutability"):
        failures.append("multi_module deep immutability failed")
    if not isinstance(value.get("rework_loops"), int):
        failures.append(f"{key} rework_loops is required")
    if not value.get("raw_evidence"):
        failures.append(f"{key} raw evidence is required")
    return value


def _scenario_identity(scenario_id: str) -> dict:
    manifest = json.loads(_scenario_manifest_path(scenario_id).read_text(encoding="utf-8"))
    identity = {
        "base_sha": manifest["base_sha"],
        "acceptance_command": manifest["acceptance_command"],
    }
    if manifest.get("deep_immutability_command"):
        identity["deep_immutability_command"] = manifest["deep_immutability_command"]
    return identity


def _scenario_manifest_sha256(scenario_id: str) -> str:
    return hashlib.sha256(_scenario_manifest_path(scenario_id).read_bytes()).hexdigest()


def _scenario_manifest_path(scenario_id: str) -> Path:
    return SCENARIO_DIR / f"{scenario_id}.json"


def _verify_source_digest(root: Path, item: dict) -> None:
    source = root / item["source"]
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != item["source_sha256"]:
        raise PerformanceError(f"source digest mismatch: {item['source']}")


def _git_head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
    ).strip()


def _load_previous(paths: list[Path]) -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=Path("benchmarks/frozen-superpowers-v1.json"))
    parser.add_argument("--verify-baseline", action="store_true")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--previous", type=Path, action="append", default=[])
    parser.add_argument("--previous-glob")
    args = parser.parse_args()

    try:
        if args.verify_baseline:
            digest = verify_baseline_file(args.baseline)
            print(json.dumps({"status": "pass", "baseline_sha256": digest}))
            return 0
        if args.candidate is None:
            raise PerformanceError("--candidate is required unless --verify-baseline is used")
        baseline = load_frozen_baseline(args.baseline)
        candidate = load_candidate(args.candidate)
        previous = _load_previous(args.previous)
        if args.previous_glob:
            previous.extend(load_previous_glob(args.previous_glob, args.candidate))
        result = validate_candidate(baseline, candidate, previous)
        if args.output:
            root = Path.cwd()
            expected = f"{_git_head(root)}.json"
            if args.output.name != expected:
                raise PerformanceError(f"output filename must be {expected}")
            if args.output.exists():
                raise PerformanceError(f"result already exists: {args.output}")
            value = {"schema_version": "herdr-performance-result/v1", **result}
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, subprocess.CalledProcessError, PerformanceError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
