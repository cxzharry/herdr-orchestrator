#!/usr/bin/env python3
"""Create a normalized Standard-gate control state from one lane manifest."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

try:
    from scripts.scheduler_state import normalize_lane
except ModuleNotFoundError:
    from scheduler_state import normalize_lane


class StateCreationError(RuntimeError):
    pass


RUN_FIELDS = {
    "schema_version",
    "contract_id",
    "root",
    "base_sha",
    "approved_input_sha256",
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


def create_state(manifest_path: Path, state_path: Path) -> dict:
    if state_path.exists():
        raise StateCreationError(f"control state already exists: {state_path}")
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

    run_dir = state_path.parent
    lanes = {}
    for source in manifest["lanes"]:
        lane_missing = LANE_FIELDS - set(source)
        if lane_missing:
            raise StateCreationError(
                "lane missing fields: " + ", ".join(sorted(lane_missing))
            )
        lane_id = source["lane_id"]
        if lane_id in lanes:
            raise StateCreationError(f"duplicate lane: {lane_id}")
        lane = normalize_lane(manifest, lane_id, source, run_dir)
        lanes[lane_id] = lane

    value = {
        "schema_version": "herdr-control-state/v2",
        "contract_id": manifest["contract_id"],
        "root": manifest["root"],
        "base_sha": manifest["base_sha"],
        "approved_input_sha256": manifest["approved_input_sha256"],
        "revision": 0,
        "controller": manifest.get("controller", {}),
        "requests": {},
        "request_order": [],
        "event_cursor": 0,
        "watcher": manifest.get("watcher", {}),
        "lanes": lanes,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "receipts").mkdir(exist_ok=True)
    (run_dir / "evidence").mkdir(exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{state_path.name}.", dir=run_dir, text=True
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
