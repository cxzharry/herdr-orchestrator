#!/usr/bin/env python3
"""Write a validator-clean terminal receipt from current control-state identity."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.validate_lane_receipt import REVIEWER_ROLES, validate_receipt
except ModuleNotFoundError:
    from validate_lane_receipt import REVIEWER_ROLES, validate_receipt


class ReceiptWriteError(RuntimeError):
    pass


def write_receipt(
    state_path: Path,
    lane_id: str,
    status: str,
    *,
    output_identity: dict | None,
    covered_acceptance: list[str],
    checks: list[dict],
    finding_or_blocker: dict | None = None,
    resume_condition: str | None = None,
) -> dict:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    lane = state.get("lanes", {}).get(lane_id)
    if lane is None:
        raise ReceiptWriteError(f"unknown lane: {lane_id}")
    if output_identity is None and lane["role"] in REVIEWER_ROLES:
        output_identity = lane["input_identity"]

    value = {
        "schema_version": "herdr-lane-receipt/v1",
        "contract_id": state["contract_id"],
        "lane_id": lane_id,
        "generation": lane["generation"],
        "role": lane["role"],
        "agent_name": lane["agent_name"],
        "pane_id": lane["pane_id"],
        "session_id": lane["session_id"],
        "status": status,
        "root": state.get("root"),
        "completed_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "input_identity": lane["input_identity"],
        "output_identity": output_identity or {},
        "covered_acceptance": covered_acceptance,
        "checks": checks,
        "finding_or_blocker": finding_or_blocker,
        "resume_condition": resume_condition,
    }
    failures = validate_receipt(value, state)
    if failures:
        raise ReceiptWriteError("; ".join(failures))

    receipt_path = Path(lane["receipt_path"])
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{receipt_path.name}.", dir=receipt_path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
        os.replace(temporary, receipt_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return value


def _pairs(items: list[str]) -> dict[str, str]:
    result = {}
    for item in items:
        key, value = item.split("=", 1)
        result[key] = value
    return result


def _checks(items: list[str]) -> list[dict]:
    values = []
    for item in items:
        command, result = item.rsplit("=", 1)
        values.append({"command": command, "result": result.lower()})
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-state", type=Path, required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--status", choices=("PASS", "FINDING", "BLOCKED"), required=True)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--output", action="append", default=[])
    output.add_argument("--output-json", type=Path)
    parser.add_argument("--acceptance", action="append", default=[])
    parser.add_argument("--check", action="append", default=[])
    parser.add_argument("--finding-json", type=Path)
    parser.add_argument("--resume-condition")
    args = parser.parse_args()

    try:
        output_identity = (
            json.loads(args.output_json.read_text(encoding="utf-8"))
            if args.output_json
            else (_pairs(args.output) if args.output else None)
        )
        finding = (
            json.loads(args.finding_json.read_text(encoding="utf-8"))
            if args.finding_json
            else None
        )
        value = write_receipt(
            args.control_state,
            args.lane,
            args.status,
            output_identity=output_identity,
            covered_acceptance=args.acceptance,
            checks=_checks(args.check),
            finding_or_blocker=finding,
            resume_condition=args.resume_condition,
        )
    except (OSError, ValueError, ReceiptWriteError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 1
    print(
        json.dumps(
            {
                "status": "written",
                "receipt_path": str(
                    json.loads(
                        args.control_state.read_text(encoding="utf-8")
                    )["lanes"][args.lane]["receipt_path"]
                ),
                "generation": value["generation"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
