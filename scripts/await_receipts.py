#!/usr/bin/env python3
"""Wait on current receipt files instead of waiting on agent chat state."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

try:
    from scripts.validate_lane_receipt import validate_receipt
except ModuleNotFoundError:
    from validate_lane_receipt import validate_receipt


class ReceiptWaitError(RuntimeError):
    pass


def await_lanes(
    state_path: Path,
    lane_ids: list[str],
    timeout: float,
    poll: float = 0.1,
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        terminal = {}
        for lane_id in lane_ids:
            lane = state.get("lanes", {}).get(lane_id)
            if lane is None:
                raise ReceiptWaitError(f"unknown lane: {lane_id}")
            receipt_path = Path(lane["receipt_path"])
            if not receipt_path.is_file():
                continue
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            failures = validate_receipt(receipt, state)
            if failures:
                raise ReceiptWaitError(
                    f"{lane_id} receipt invalid: " + "; ".join(failures)
                )
            terminal[lane_id] = receipt["status"]
        if len(terminal) == len(lane_ids):
            return {"status": "terminal", "lanes": terminal}
        time.sleep(poll)
    missing = sorted(set(lane_ids) - set(terminal))
    raise ReceiptWaitError("timed out waiting for: " + ", ".join(missing))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-state", type=Path, required=True)
    parser.add_argument("--lane", action="append", dest="lanes", required=True)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--poll", type=float, default=0.1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = await_lanes(
            args.control_state,
            args.lanes,
            args.timeout,
            args.poll,
        )
    except (OSError, ValueError, ReceiptWaitError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
