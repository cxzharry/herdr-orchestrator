#!/usr/bin/env python3
"""Validate replacement benchmark results against frozen baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


class PerformanceError(RuntimeError):
    pass


def load_frozen_baseline(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "herdr-frozen-superpowers/v1":
        raise PerformanceError("unsupported frozen baseline")
    _verify_source_digest(path.parent.parent, value["compact"])
    _verify_source_digest(path.parent.parent, value["multi_module"])
    return value


def validate_candidate(baseline: dict, candidate: dict, previous: list[dict]) -> dict:
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
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous", type=Path, action="append", default=[])
    args = parser.parse_args()

    try:
        root = Path.cwd()
        expected = f"{_git_head(root)}.json"
        if args.output.name != expected:
            raise PerformanceError(f"output filename must be {expected}")
        if args.output.exists():
            raise PerformanceError(f"result already exists: {args.output}")

        baseline = load_frozen_baseline(args.baseline)
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        result = validate_candidate(baseline, candidate, _load_previous(args.previous))
        value = {"schema_version": "herdr-performance-result/v1", **result}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, subprocess.CalledProcessError, PerformanceError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 1

    print(json.dumps({"status": "pass", "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
