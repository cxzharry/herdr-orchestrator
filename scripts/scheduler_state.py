#!/usr/bin/env python3
"""Atomic scheduler-state helpers for persistent P1 control-state v2."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Callable


PLAN_REQUIRED_TYPES = {
    "architecture",
    "public_contract",
    "security",
    "auth",
    "rbac",
    "schema",
    "migration",
    "production_topology",
    "ambiguous_product_behavior",
}
TERMINAL_STATES = {"ACCEPTED", "PASS", "FINDING", "BLOCKED", "SUPERSEDED"}
READY_STATES = {"READY"}
SCHEDULER_LANES = {"p2", "p3", "p4", "p5"}


class SchedulerStateError(RuntimeError):
    pass


def read_state(state_path: Path) -> dict:
    return upgrade_state(json.loads(state_path.read_text(encoding="utf-8")))


def upgrade_state(value: dict) -> dict:
    schema = value.get("schema_version")
    if schema not in {None, "herdr-control-state/v1", "herdr-control-state/v2"}:
        raise SchedulerStateError("unsupported control-state schema_version")
    upgraded = copy.deepcopy(value)
    upgraded["schema_version"] = "herdr-control-state/v2"
    upgraded.setdefault("revision", 0)
    upgraded.setdefault("controller", {})
    upgraded.setdefault("requests", {})
    upgraded.setdefault("request_order", [])
    upgraded.setdefault("event_cursor", 0)
    upgraded.setdefault("watcher", {})
    upgraded.setdefault("lanes", {})
    for lane_id, lane in upgraded["lanes"].items():
        _normalize_existing_lane(upgraded, lane_id, lane)
    return upgraded


def normalize_lane(run_state: dict, lane_id: str, source: dict, run_dir: Path) -> dict:
    generation = source["generation"]
    lane = copy.deepcopy(source)
    lane.update(
        {
            "lane_id": lane_id,
            "contract_id": run_state["contract_id"],
            "root": run_state.get("root"),
            "base_sha": run_state.get("base_sha"),
            "state": source.get("state", "READY"),
            "receipt_path": source.get(
                "receipt_path",
                str(run_dir / "receipts" / f"{lane_id}-g{generation}.json"),
            ),
        }
    )
    lane.setdefault("owned_scope", [])
    lane.setdefault("dependencies", [])
    lane.setdefault("blocked_by", [])
    return lane


def atomic_update(state_path: Path, mutator: Callable[[dict], object]) -> object:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = state_path.with_suffix(state_path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        value = read_state(state_path)
        before = json.dumps(value, sort_keys=True, separators=(",", ":"))
        result = mutator(value)
        after = json.dumps(value, sort_keys=True, separators=(",", ":"))
        if after != before:
            value["revision"] = int(value.get("revision", 0)) + 1
            _write_json_atomic(state_path, value)
        return result


def set_lane(
    state_path: Path,
    lane_id: str,
    generation: int,
    state_value: str,
    receipt_path: str,
    input_updates: dict[str, str],
    *,
    owned_scope: list[str] | None = None,
) -> dict:
    def mutate(value: dict) -> dict:
        lane = value.get("lanes", {}).get(lane_id)
        if lane is None:
            raise SchedulerStateError(f"unknown lane: {lane_id}")
        lane["generation"] = generation
        lane["state"] = state_value
        lane["receipt_path"] = receipt_path
        lane["contract_id"] = value["contract_id"]
        lane["root"] = value.get("root")
        lane["base_sha"] = value.get("base_sha")
        lane.setdefault("owned_scope", [])
        if owned_scope is not None:
            lane["owned_scope"] = list(owned_scope)
        lane.setdefault("input_identity", {}).update(input_updates)
        return copy.deepcopy(lane)

    return atomic_update(state_path, mutate)


def classify_delta(request: dict) -> str:
    markers = {request.get("change_type")}
    markers.update(request.get("risk_markers", []))
    if PLAN_REQUIRED_TYPES.intersection(markers):
        return "PLAN_REQUIRED"
    affected_paths = request.get("affected_paths")
    if not affected_paths:
        return "ANALYSIS_REQUIRED"
    return "READY"


def register_delta(state_path: Path, request: dict) -> dict:
    request_id = request["request_id"]

    def mutate(value: dict) -> dict:
        existing = value["requests"].get(request_id)
        if existing is not None:
            return copy.deepcopy(existing["result"])

        record = _request_record(request)
        value["requests"][request_id] = record
        value["request_order"].append(request_id)

        classification = classify_delta(record)
        if classification == "PLAN_REQUIRED":
            result = {"status": "PLAN_REQUIRED", "request_id": request_id}
            _finish_request(record, result, "PLAN_REQUIRED")
            return copy.deepcopy(result)
        if classification == "ANALYSIS_REQUIRED":
            result = {"status": "ANALYSIS_REQUIRED", "request_id": request_id}
            record["analysis_only"] = True
            _finish_request(record, result, "ANALYSIS_REQUIRED")
            return copy.deepcopy(result)

        dependency_blockers = _dependency_blockers(value, record)
        ownership_blockers = _ownership_blockers(value, record["affected_paths"])
        blockers = sorted(set(dependency_blockers + ownership_blockers))
        if blockers:
            result = {
                "status": "DEPENDENCY_BLOCKED",
                "request_id": request_id,
                "blocked_by": blockers,
            }
            record["blocked_by"] = blockers
            _finish_request(record, result, "DEPENDENCY_BLOCKED")
            return copy.deepcopy(result)

        lane = _next_idle_lane(value)
        if lane is None:
            result = {"status": "CAPACITY_BLOCKED", "request_id": request_id}
            _finish_request(record, result, "CAPACITY_BLOCKED")
            return copy.deepcopy(result)

        lane["state"] = "ACTIVE"
        lane["owned_scope"] = list(record["affected_paths"])
        lane["input_identity"] = copy.deepcopy(record["input_identity"])
        lane["contract_id"] = value["contract_id"]
        lane["root"] = value.get("root")
        lane["base_sha"] = value.get("base_sha")
        result = {
            "status": "DISPATCH",
            "request_id": request_id,
            "lane_id": lane["lane_id"],
            "generation": lane["generation"],
        }
        record["lane_id"] = lane["lane_id"]
        _finish_request(record, result, "ACTIVE")
        return copy.deepcopy(result)

    return atomic_update(state_path, mutate)


def _normalize_existing_lane(state: dict, lane_id: str, lane: dict) -> None:
    lane.setdefault("lane_id", lane_id)
    lane.setdefault("contract_id", state.get("contract_id"))
    lane.setdefault("root", state.get("root"))
    lane.setdefault("base_sha", state.get("base_sha"))
    lane.setdefault("owned_scope", [])
    lane.setdefault("dependencies", [])
    lane.setdefault("blocked_by", [])


def _request_record(request: dict) -> dict:
    return {
        "request_id": request["request_id"],
        "summary": request.get("summary", ""),
        "change_type": request.get("change_type", "code"),
        "affected_paths": copy.deepcopy(request.get("affected_paths")),
        "input_identity": copy.deepcopy(request.get("input_identity", {})),
        "dependencies": list(request.get("dependencies", [])),
        "risk_markers": list(request.get("risk_markers", [])),
        "state": "READY",
        "blocked_by": [],
        "analysis_only": False,
    }


def _finish_request(record: dict, result: dict, state: str) -> None:
    record["state"] = state
    record["result"] = copy.deepcopy(result)


def _dependency_blockers(state: dict, request: dict) -> list[str]:
    blockers = []
    for lane_id in request.get("dependencies", []):
        lane = state.get("lanes", {}).get(lane_id)
        if lane is None or lane.get("state") not in TERMINAL_STATES:
            blockers.append(lane_id)
    return blockers


def _ownership_blockers(state: dict, paths: list[str]) -> list[str]:
    blockers = []
    for lane_id, lane in state.get("lanes", {}).items():
        if lane.get("state") != "ACTIVE":
            continue
        if _paths_overlap(paths, lane.get("owned_scope", [])):
            blockers.append(lane_id)
    return blockers


def _paths_overlap(left: list[str], right: list[str]) -> bool:
    for first in left:
        for second in right:
            if _path_overlaps(first, second):
                return True
    return False


def _path_overlaps(first: str, second: str) -> bool:
    first = first.strip("/")
    second = second.strip("/")
    return first == second or first.startswith(second + "/") or second.startswith(first + "/")


def _next_idle_lane(state: dict) -> dict | None:
    for lane_id in sorted(state.get("lanes", {})):
        lane = state["lanes"][lane_id]
        if lane_id in SCHEDULER_LANES and lane.get("state") in READY_STATES:
            return lane
    return None


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
