#!/usr/bin/env python3
"""Atomically update one explicit lane without hand-editing control state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.scheduler_state import SchedulerStateError, set_lane as set_scheduler_lane
except ModuleNotFoundError:
    from scheduler_state import SchedulerStateError, set_lane as set_scheduler_lane


class StateUpdateError(RuntimeError):
    pass


def set_lane(
    state_path: Path,
    lane_id: str,
    generation: int,
    state_value: str,
    receipt_path: str,
    input_updates: dict[str, str],
) -> dict:
    try:
        return set_scheduler_lane(
            state_path,
            lane_id,
            generation,
            state_value,
            receipt_path,
            input_updates,
        )
    except SchedulerStateError as error:
        raise StateUpdateError(str(error)) from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-state", type=Path, required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--generation", type=int, required=True)
    parser.add_argument("--state", dest="state_value", required=True)
    parser.add_argument("--receipt-path", required=True)
    parser.add_argument("--input", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    updates = {}
    try:
        for item in args.input:
            key, value = item.split("=", 1)
            updates[key] = value
        lane = set_lane(
            args.control_state,
            args.lane,
            args.generation,
            args.state_value,
            args.receipt_path,
            updates,
        )
    except (OSError, ValueError, StateUpdateError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, indent=2))
        return 1
    print(json.dumps({"status": "updated", "lane": lane}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
