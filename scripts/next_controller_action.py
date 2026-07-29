#!/usr/bin/env python3
"""Return one bounded post-compaction controller scheduler action."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def next_controller_action(state: dict[str, Any]) -> dict[str, Any]:
    scope = state.get("controller_scope")
    if not scope:
        return _blocked(scope, "missing controller_scope")
    matrix = state.get("gate_matrix")
    if not isinstance(matrix, dict):
        return _blocked(scope, "missing gate_matrix")
    mode = matrix.get("mode")
    if mode == "Compact":
        return {
            "action": "DISPATCH_COMPACT_VERIFIER",
            "controller_scope": scope,
        }
    if mode != "Standard":
        return _blocked(scope, "unknown gate mode")

    applicable = matrix.get("applicable") or {}
    prereq = state.get("prerequisites") or {}
    lanes = state.get("lanes") or {}
    if not prereq.get("implementation_receipts_accepted"):
        return _blocked(scope, "implementation receipts are not accepted")

    p5 = _lane_for_slot(lanes, "P5")
    if applicable.get("P5") and not _accepted(p5):
        return {
            "action": "DISPATCH_GATE",
            "controller_scope": scope,
            "slot": "P5",
            "role": (p5 or {}).get("role", "integration-owner"),
        }

    if prereq.get("integration_artifact_ready"):
        first_wave = []
        p6 = _lane_for_slot(lanes, "P6")
        if applicable.get("P6") and not _accepted(p6):
            if applicable.get("P5") and _accepted(p5):
                first_wave.append({"slot": "P5", "role": "smoke"})
            first_wave.append({"slot": "P6", "role": (p6 or {}).get("role", "integration-reviewer")})
        if first_wave:
            return {
                "action": "DISPATCH_PARALLEL_GATES",
                "controller_scope": scope,
                "gates": first_wave,
            }

        if prereq.get("local_runtime_ready") or prereq.get("deployment_ready"):
            gates = []
            for slot in ("P7", "P8", "P9"):
                lane = _lane_for_slot(lanes, slot)
                if applicable.get(slot) and not _accepted(lane):
                    gates.append({"slot": slot, "role": (lane or {}).get("role")})
            if gates:
                return {
                    "action": "DISPATCH_PARALLEL_GATES",
                    "controller_scope": scope,
                    "gates": gates,
                }
        return _blocked(scope, "review prerequisites are incomplete")

    return _blocked(scope, "integration artifact is not ready")


def _accepted(lane: dict[str, Any] | None) -> bool:
    return bool(lane and lane.get("state") in {"ACCEPTED", "PASS"})


def _lane_for_slot(lanes: dict[str, Any], slot: str) -> dict[str, Any] | None:
    for lane in lanes.values():
        if lane.get("slot") == slot:
            return lane
    return None


def _blocked(scope: str | None, reason: str) -> dict[str, Any]:
    return {
        "action": "BLOCKED_STATE",
        "controller_scope": scope,
        "reason": reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-state", type=Path, required=True)
    args = parser.parse_args()
    state = json.loads(args.control_state.read_text(encoding="utf-8"))
    print(json.dumps(next_controller_action(state), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
