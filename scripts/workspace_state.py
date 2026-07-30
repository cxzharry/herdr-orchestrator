#!/usr/bin/env python3
"""Single mutable Herdr workspace ledger."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Callable

try:
    from scripts.herdr_identity import ROLE_NAMES
except ModuleNotFoundError:
    from herdr_identity import ROLE_NAMES


SCHEMA = "herdr-workspace-state/v1"
IMPLEMENTATION_SLOTS = ("P2", "P3", "P4")
TERMINAL_LANE_STATES = {
    "ACCEPTED", "FINDING", "BLOCKED", "LOST", "SUPERSEDED"
}


class StateError(RuntimeError):
    pass


def initial_state(workspace_id: str, controller: dict | None = None) -> dict:
    return {
        "schema_version": SCHEMA,
        "workspace_id": workspace_id,
        "revision": 0,
        "controller": controller or {},
        "slots": {
            slot: {
                "role_name": ROLE_NAMES[slot],
                "session_id": None,
                "pane_id": None,
                "status": "COLD",
                "misses": 0,
            }
            for slot in ROLE_NAMES
        },
        "run": {},
        "lanes": {},
        "requests": {},
        "request_order": [],
        "inbox": [],
        "queues": {"ownership": [], "capacity": []},
        "watcher": {
            "watcher_id": None,
            "heartbeat_at": None,
            "wake_verified_at": None,
        },
        "events": [],
        "event_cursor": 0,
    }


def load_state(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != SCHEMA:
        raise StateError("unsupported workspace state schema_version")
    return value


def create_state(
    path: Path,
    workspace_id: str,
    *,
    controller: dict | None = None,
    run: dict | None = None,
    lanes: list[dict] | None = None,
) -> dict:
    if path.exists():
        raise StateError(f"workspace state already exists: {path}")
    value = initial_state(workspace_id, controller=controller)
    value["run"] = copy.deepcopy(run or {})
    for lane in lanes or []:
        lane_id = lane["lane_id"]
        if lane_id in value["lanes"]:
            raise StateError(f"lane already exists: {lane_id}")
        value["lanes"][lane_id] = _normalize_lane(value, lane)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(path, value)
    return load_state(path)


def mutate_state(path: Path, mutator: Callable[[dict], object]) -> object:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        value = load_state(path)
        before = _canonical(value)
        result = mutator(value)
        after = _canonical(value)
        if after != before:
            value["revision"] = int(value.get("revision", 0)) + 1
            _write_json_atomic(path, value)
        return result


def append_inbox(path: Path, item: dict) -> dict:
    def mutate(value: dict) -> dict:
        value["inbox"].append(copy.deepcopy(item))
        return copy.deepcopy(item)

    return mutate_state(path, mutate)


def append_observation(path: Path, event: dict) -> dict:
    def mutate(value: dict) -> dict:
        value["event_cursor"] = int(value.get("event_cursor", 0)) + 1
        record = {"cursor": value["event_cursor"], **copy.deepcopy(event)}
        value["events"].append(record)
        return copy.deepcopy(record)

    return mutate_state(path, mutate)


def apply_controller_tick(path: Path, tick: dict) -> dict:
    def mutate(value: dict) -> dict:
        value["run"].update(copy.deepcopy(tick))
        return copy.deepcopy(value["run"])

    return mutate_state(path, mutate)


def register_lane(path: Path, lane: dict) -> dict:
    def mutate(value: dict) -> dict:
        lane_id = lane["lane_id"]
        if lane_id in value["lanes"]:
            raise StateError(f"lane already exists: {lane_id}")
        normalized = _normalize_lane(value, lane)
        value["lanes"][lane_id] = normalized
        return copy.deepcopy(normalized)

    return mutate_state(path, mutate)


def transition_lane(
    path: Path,
    lane_id: str,
    generation: int,
    state: str,
    *,
    receipt_path: str | None = None,
    input_updates: dict[str, str] | None = None,
    output_artifact: dict | None = None,
    verification: list[dict] | None = None,
) -> dict:
    def mutate(value: dict) -> dict:
        lane = value["lanes"].get(lane_id)
        if lane is None:
            raise StateError(f"unknown lane: {lane_id}")
        if lane.get("generation") != generation:
            raise StateError("generation does not match current lane")
        lane["state"] = state
        if receipt_path is not None:
            lane["receipt_path"] = receipt_path
        if input_updates:
            lane.setdefault("input_identity", {}).update(input_updates)
        if output_artifact is not None:
            lane["output_artifact"] = copy.deepcopy(output_artifact)
        if verification is not None:
            lane["verification"] = copy.deepcopy(verification)
        return copy.deepcopy(lane)

    return mutate_state(path, mutate)


def _normalize_lane(state: dict, source: dict) -> dict:
    lane_id = source["lane_id"]
    generation = int(source.get("generation", 1))
    run = state.get("run", {})
    lane = {
        "lane_id": lane_id,
        "contract_id": source.get("contract_id", run.get("contract_id")),
        "generation": generation,
        "role": source.get("role", "implementation"),
        "agent_name": source.get("agent_name", ""),
        "session_id": source.get("session_id"),
        "state": source.get("state", "READY"),
        "input_identity": copy.deepcopy(source.get("input_identity", {})),
        "receipt_path": source.get(
            "receipt_path",
            str(Path(run.get("run_dir", ".")) / "receipts" / f"{lane_id}-g{generation}.json"),
        ),
        "owned_scope": list(source.get("owned_scope", [])),
    }
    for key in ("root", "base_sha", "approved_input_sha256"):
        if key in source:
            lane[key] = source[key]
        elif key in run:
            lane[key] = run[key]
    return lane


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _write_json_atomic(path: Path, value: dict) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
