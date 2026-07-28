#!/usr/bin/env python3
"""Atomically update one explicit lane without hand-editing control state."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


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
    value = json.loads(state_path.read_text(encoding="utf-8"))
    lane = value.get("lanes", {}).get(lane_id)
    if lane is None:
        raise StateUpdateError(f"unknown lane: {lane_id}")
    lane["generation"] = generation
    lane["state"] = state_value
    lane["receipt_path"] = receipt_path
    lane.setdefault("input_identity", {}).update(input_updates)

    state_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{state_path.name}.",
        dir=state_path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
        os.replace(temporary, state_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return lane


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
