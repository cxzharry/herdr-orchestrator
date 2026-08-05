#!/usr/bin/env python3
"""Create a Herdr workspace ledger from one lane manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.delivery_mode import validate_mode
    from scripts.workspace_state import StateError, create_state as create_workspace_state
except ModuleNotFoundError:
    from delivery_mode import validate_mode
    from workspace_state import StateError, create_state as create_workspace_state


class StateCreationError(RuntimeError):
    pass


RUN_FIELDS = {
    "schema_version",
    "contract_id",
    "root",
    "base_sha",
    "approved_input_sha256",
    "mode",
    "risk",
    "review_applicability",
    "lanes",
}
LANE_FIELDS = {
    "lane_id",
    "generation",
    "role",
    "agent_name",
    "pane_id",
    "session_id",
    "input_identity",
    "owned_scope",
}
MANDATORY_LANE_ROLES = {
    "integration": "P5 integration",
    "integration-reviewer": "P6 independent-review",
}


def create_state(manifest_path: Path, state_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing = RUN_FIELDS - set(manifest)
    if missing:
        raise StateCreationError(
            f"manifest missing fields: {', '.join(sorted(missing))}"
        )
    if manifest["schema_version"] != "herdr-run-manifest/v1":
        raise StateCreationError("unsupported manifest schema_version")
    if not isinstance(manifest["lanes"], list) or not manifest["lanes"]:
        raise StateCreationError("manifest lanes must be a non-empty list")

    lanes = []
    for source in manifest["lanes"]:
        lane_missing = LANE_FIELDS - set(source)
        if lane_missing:
            raise StateCreationError(
                "lane missing fields: " + ", ".join(sorted(lane_missing))
            )
        lane_id = source["lane_id"]
        if any(item["lane_id"] == lane_id for item in lanes):
            raise StateCreationError(f"duplicate lane: {lane_id}")
        lanes.append(dict(source))

    for role, label in MANDATORY_LANE_ROLES.items():
        count = sum(lane["role"] == role for lane in lanes)
        if count != 1:
            raise StateCreationError(
                f"manifest requires exactly one {label} lane "
                f"(role={role}); found {count}"
            )

    try:
        validate_mode(
            manifest["mode"],
            manifest["risk"],
            manifest["review_applicability"],
            sum(lane["role"] == "implementation" for lane in lanes),
        )
    except ValueError as error:
        raise StateCreationError(str(error)) from error

    run = {
        "contract_id": manifest["contract_id"],
        "root": manifest["root"],
        "base_sha": manifest["base_sha"],
        "approved_input_sha256": manifest["approved_input_sha256"],
        "mode": manifest["mode"],
        "risk": dict(manifest["risk"]),
        "review_applicability": dict(manifest["review_applicability"]),
        "run_dir": str(state_path.parent),
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    (state_path.parent / "receipts").mkdir(exist_ok=True)
    (state_path.parent / "evidence").mkdir(exist_ok=True)
    try:
        return create_workspace_state(
            state_path,
            manifest.get("workspace_id", "workspace"),
            controller=manifest.get("controller", {}),
            run=run,
            lanes=lanes,
        )
    except StateError as error:
        raise StateCreationError(str(error)) from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--control-state", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = create_state(args.manifest, args.control_state)
    except (OSError, ValueError, StateCreationError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 1
    print(
        json.dumps(
            {
                "status": "created",
                "control_state": str(args.control_state),
                "lanes": sorted(value["lanes"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
