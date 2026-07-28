#!/usr/bin/env python3
"""Atomically register one newly started Standard-gate lane."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

try:
    from scripts.create_control_state import LANE_FIELDS
except ModuleNotFoundError:
    from create_control_state import LANE_FIELDS


class LaneRegistrationError(RuntimeError):
    pass


def register_lane(state_path: Path, lane_path: Path) -> dict:
    value = json.loads(state_path.read_text(encoding="utf-8"))
    source = json.loads(lane_path.read_text(encoding="utf-8"))
    missing = LANE_FIELDS - set(source)
    if missing:
        raise LaneRegistrationError(
            "lane missing fields: " + ", ".join(sorted(missing))
        )
    lane_id = source["lane_id"]
    if lane_id in value.get("lanes", {}):
        raise LaneRegistrationError(f"lane already exists: {lane_id}")

    generation = source["generation"]
    lane = dict(source)
    lane.update(
        {
            "contract_id": value["contract_id"],
            "state": source.get("state", "READY"),
            "receipt_path": source.get(
                "receipt_path",
                str(
                    state_path.parent
                    / "receipts"
                    / f"{lane_id}-g{generation}.json"
                ),
            ),
        }
    )
    value.setdefault("lanes", {})[lane_id] = lane
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{state_path.name}.", dir=state_path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
        os.replace(temporary, state_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return value


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
