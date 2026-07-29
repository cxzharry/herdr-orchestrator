#!/usr/bin/env python3
"""Atomically register one newly started Standard-gate lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.create_control_state import LANE_FIELDS
    from scripts.scheduler_state import atomic_update, normalize_lane
except ModuleNotFoundError:
    from create_control_state import LANE_FIELDS
    from scheduler_state import atomic_update, normalize_lane


class LaneRegistrationError(RuntimeError):
    pass


def register_lane(state_path: Path, lane_path: Path) -> dict:
    source = json.loads(lane_path.read_text(encoding="utf-8"))
    missing = LANE_FIELDS - set(source)
    if missing:
        raise LaneRegistrationError(
            "lane missing fields: " + ", ".join(sorted(missing))
        )

    def mutate(value: dict) -> dict:
        lane_id = source["lane_id"]
        if lane_id in value.get("lanes", {}):
            raise LaneRegistrationError(f"lane already exists: {lane_id}")
        lane = normalize_lane(value, lane_id, source, state_path.parent)
        value.setdefault("lanes", {})[lane_id] = lane
        return value

    return atomic_update(state_path, mutate)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-state", type=Path, required=True)
    parser.add_argument("--lane-json", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = register_lane(args.control_state, args.lane_json)
        lane_id = json.loads(
            args.lane_json.read_text(encoding="utf-8")
        )["lane_id"]
    except (OSError, ValueError, LaneRegistrationError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 1
    print(
        json.dumps(
            {"status": "registered", "lane": value["lanes"][lane_id]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
