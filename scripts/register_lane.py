#!/usr/bin/env python3
"""Atomically register one newly started Standard-gate lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.create_control_state import LANE_FIELDS
    from scripts.workspace_state import StateError, register_lane as register_workspace_lane
except ModuleNotFoundError:
    from create_control_state import LANE_FIELDS
    from workspace_state import StateError, register_lane as register_workspace_lane


class LaneRegistrationError(RuntimeError):
    pass


def register_lane(state_path: Path, lane_path: Path) -> dict:
    source = json.loads(lane_path.read_text(encoding="utf-8"))
    missing = LANE_FIELDS - set(source)
    if missing:
        raise LaneRegistrationError(
            "lane missing fields: " + ", ".join(sorted(missing))
        )

    try:
        register_workspace_lane(state_path, source)
        return json.loads(state_path.read_text(encoding="utf-8"))
    except StateError as error:
        raise LaneRegistrationError(str(error)) from error


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
