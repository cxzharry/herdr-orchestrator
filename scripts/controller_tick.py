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
STANDARD_PREWARM_SLOTS = ("P5", "P6")
REDIRECT_AFTER_SECONDS = 60
REASSIGN_AFTER_SECONDS = 120


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
    actions.extend(_emit_standard_overlap_actions(next_state))
    actions.extend(_emit_stall_actions(next_state, now))

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


def _emit_standard_overlap_actions(state: dict[str, Any]) -> list[dict[str, Any]]:
    if state.get("run", {}).get("mode") != "Standard":
        return []
    actions = []
    if _implementation_work_active(state):
        for lane_id, lane in sorted(state.get("lanes", {}).items()):
            if lane.get("state") == "ACCEPTED" and lane.get("output_artifact"):
                if state.get("slots", {}).get("P6", {}).get("status") in FREE_SLOT_STATES:
                    actions.append({"kind": "REVIEW_DIFF", "slot": "P6", "lane_id": lane_id})
                    state["slots"]["P6"]["status"] = "BUSY"
                    break
        for slot in STANDARD_PREWARM_SLOTS:
            value = state.get("slots", {}).get(slot, {})
            if value.get("status") in FREE_SLOT_STATES:
                value["status"] = "WARMING"
                actions.append({"kind": "PREWARM", "slot": slot})
    return actions


def _implementation_work_active(state: dict[str, Any]) -> bool:
    for slot in DISPATCH_SLOTS:
        if state.get("slots", {}).get(slot, {}).get("status") in ACTIVE_SLOT_STATES:
            return True
    return any(
        lane.get("state") == "ACTIVE" and lane.get("slot") in DISPATCH_SLOTS
        for lane in state.get("lanes", {}).values()
    )


def _emit_stall_actions(state: dict[str, Any], now: int | float) -> list[dict[str, Any]]:
    actions = []
    for lane_id, lane in sorted(state.get("lanes", {}).items()):
        if lane.get("state") != "ACTIVE":
            continue
        started = lane.get("active_timer_started_at", lane.get("started_at", now))
        quiet_since = lane.get("last_progress_at", started)
        quiet_for = now - quiet_since
        if quiet_for < REDIRECT_AFTER_SECONDS:
            continue
        if quiet_for >= REASSIGN_AFTER_SECONDS:
            target = _idle_compatible_slot(state, lane.get("slot"))
            if target:
                actions.append(_reassign_lane(state, lane_id, lane, target, started))
                continue
        if lane.get("redirected_at") is not None:
            continue
        lane["redirected_at"] = now
        actions.append(
            {
                "kind": "REDIRECT",
                "lane_id": lane_id,
                "slot": lane.get("slot"),
                "deadline_seconds": REDIRECT_AFTER_SECONDS,
                "timer_started_at": started,
            }
        )
    return actions


def _idle_compatible_slot(state: dict[str, Any], current_slot: str | None) -> str | None:
    for slot in DISPATCH_SLOTS:
        if slot == current_slot:
            continue
        if state.get("slots", {}).get(slot, {}).get("status") in FREE_SLOT_STATES:
            return slot
    return None


def _reassign_lane(
    state: dict[str, Any],
    lane_id: str,
    lane: dict[str, Any],
    target_slot: str,
    timer_started_at: int | float,
) -> dict[str, Any]:
    generation = int(lane.get("generation", 1)) + 1
    reassigned_id = f"{lane_id}-reassigned-g{generation}"
    source_slot = lane.get("slot")
    target = state.get("slots", {}).get(target_slot, {})
    lane["state"] = "SUPERSEDED"
    new_lane = copy.deepcopy(lane)
    new_lane.update(
        {
            "lane_id": reassigned_id,
            "generation": generation,
            "state": "ACTIVE",
            "slot": target_slot,
            "agent_name": target.get("role_name"),
            "session_id": target.get("session_id"),
            "pane_id": target.get("pane_id"),
            "workspace_id": target.get("workspace_id"),
            "active_timer_started_at": timer_started_at,
            "supersedes": lane_id,
        }
    )
    new_lane.pop("redirected_at", None)
    state.setdefault("lanes", {})[reassigned_id] = new_lane
    if source_slot in state.get("slots", {}):
        state["slots"][source_slot]["status"] = "IDLE"
        state["slots"][source_slot].pop("lane_id", None)
        state["slots"][source_slot].pop("generation", None)
    state.get("slots", {}).get(target_slot, {})["status"] = "BUSY"
    return {
        "kind": "REASSIGN",
        "lane_id": lane_id,
        "from_slot": source_slot,
        "to_slot": target_slot,
        "generation": generation,
        "timer_started_at": timer_started_at,
        "ownership_transfer": {
            "from_lane_id": lane_id,
            "to_lane_id": reassigned_id,
            "owned_scope": copy.deepcopy(lane.get("owned_scope", [])),
            "duplicate_writes_prevented": True,
        },
    }


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
