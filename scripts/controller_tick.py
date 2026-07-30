#!/usr/bin/env python3
"""Pure bounded P1 controller tick reducer."""

from __future__ import annotations

import copy
from typing import Any

try:
    from scripts.herdr_identity import agent_identity
except ModuleNotFoundError:
    from herdr_identity import agent_identity


READY_REQUEST_STATES = {"READY"}
FREE_SLOT_STATES = {"IDLE"}
ACTIVE_SLOT_STATES = {"BUSY"}
TERMINAL_LANE_STATES = {"ACCEPTED", "PASS", "FINDING", "BLOCKED", "LOST", "SUPERSEDED"}
DISPATCH_SLOTS = ("P2", "P3", "P4")


def controller_tick(
    state: dict[str, Any],
    requests: list[dict[str, Any]],
    events: list[dict[str, Any]],
    live_agents: list[dict[str, Any]],
    now: int | float,
) -> dict[str, Any]:
    next_state = copy.deepcopy(state)
    _reconcile_live(next_state, live_agents)
    _ingest_requests(next_state, requests)
    _ingest_events(next_state, events)
    actions = _emit_ready_actions(next_state)

    terminal = _delivery_terminal(next_state)
    wake_ready = _watcher_wake_proven(next_state)
    if not actions and not terminal:
        actions = [{
            "kind": "YIELD" if wake_ready else "MONITOR",
            "timeout_seconds": 30,
        }]
    return {
        "state": next_state,
        "actions": actions,
        "may_yield": bool(not terminal and wake_ready),
        "assistant_may_finalize": terminal or _real_user_blocker(next_state),
    }


def _reconcile_live(state: dict[str, Any], live_agents: list[dict[str, Any]]) -> None:
    by_session = {
        identity["session_id"]: identity
        for identity in (agent_identity(agent) for agent in live_agents)
        if identity.get("session_id")
    }
    for slot in state.get("slots", {}).values():
        session_id = slot.get("session_id")
        if not session_id or session_id not in by_session:
            continue
        live = by_session[session_id]
        if live.get("agent_status"):
            slot["status"] = _slot_status(live["agent_status"])
        elif live.get("status"):
            slot["status"] = _slot_status(live["status"])


def _ingest_requests(state: dict[str, Any], requests: list[dict[str, Any]]) -> None:
    stored = state.setdefault("requests", {})
    order = state.setdefault("request_order", [])
    for request in requests:
        request_id = request["request_id"]
        if request_id in stored:
            continue
        stored[request_id] = copy.deepcopy(request)
        stored[request_id].setdefault("state", "READY")
        order.append(request_id)


def _ingest_events(state: dict[str, Any], events: list[dict[str, Any]]) -> None:
    queued = state.setdefault("events", [])
    seen = {event.get("event_id") for event in queued if event.get("event_id")}
    for event in events:
        if event.get("event_id") in seen:
            continue
        queued.append(copy.deepcopy(event))


def _emit_ready_actions(state: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    for request_id in list(state.get("request_order", [])):
        request = state["requests"][request_id]
        if request.get("state") not in READY_REQUEST_STATES:
            continue
        slot = _next_free_slot(state)
        if slot is None:
            state.setdefault("queues", {}).setdefault("capacity", []).append(request_id)
            request["state"] = "CAPACITY_QUEUED"
            continue
        if _overlaps_active_lane(state, request.get("affected_paths") or []):
            state.setdefault("queues", {}).setdefault("ownership", []).append(request_id)
            request["state"] = "OWNERSHIP_QUEUED"
            continue
        request["state"] = "DISPATCHED"
        state["slots"][slot]["status"] = "BUSY"
        state["slots"][slot]["task_summary"] = request.get("summary") or request_id
        actions.append(
            {
                "kind": "DISPATCH",
                "slot": slot,
                "request_id": request_id,
                "agent_name": state["slots"][slot].get("role_name"),
            }
        )
    return actions


def _next_free_slot(state: dict[str, Any]) -> str | None:
    for slot in DISPATCH_SLOTS:
        if state.get("slots", {}).get(slot, {}).get("status") in FREE_SLOT_STATES:
            return slot
    return None


def _overlaps_active_lane(state: dict[str, Any], paths: list[str]) -> bool:
    for lane in state.get("lanes", {}).values():
        if lane.get("state") not in {"ACTIVE"}:
            continue
        if _paths_overlap(paths, lane.get("owned_scope", [])):
            return True
    return False


def _paths_overlap(left: list[str], right: list[str]) -> bool:
    for first in left:
        for second in right:
            first_clean = first.rstrip("*").strip("/")
            second_clean = second.rstrip("*").strip("/")
            if (
                first_clean == second_clean
                or first_clean.startswith(second_clean + "/")
                or second_clean.startswith(first_clean + "/")
            ):
                return True
    return False


def _delivery_terminal(state: dict[str, Any]) -> bool:
    lanes = state.get("lanes", {})
    if lanes:
        return all(lane.get("state") in TERMINAL_LANE_STATES for lane in lanes.values())
    if state.get("run", {}).get("status") == "ACTIVE":
        return False
    return False


def _watcher_wake_proven(state: dict[str, Any]) -> bool:
    watcher = state.get("watcher", {})
    return bool(watcher.get("heartbeat_at") and watcher.get("wake_verified_at"))


def _real_user_blocker(state: dict[str, Any]) -> bool:
    return state.get("run", {}).get("status") == "BLOCKED_USER"


def _slot_status(agent_status: str) -> str:
    return "IDLE" if agent_status in {"idle", "done"} else "BUSY"
