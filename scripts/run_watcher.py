#!/usr/bin/env python3
"""Run-scoped Herdr lane watcher with immutable event output."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.await_receipts import reconcile_once as receipt_reconcile_once
    from scripts.scheduler_state import atomic_update, read_state
except ModuleNotFoundError:
    from await_receipts import reconcile_once as receipt_reconcile_once
    from scheduler_state import atomic_update, read_state


TERMINAL_EVENT_TYPES = {"RECEIPT", "LANE_LOST"}
SETTLED_P1_STATUSES = {"idle", "done"}


class WatcherError(RuntimeError):
    pass


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def list_live_agents() -> list[dict[str, Any]]:
    result = subprocess.run(
        ["herdr", "agent", "list"],
        check=False,
        capture_output=True,
        text=True,
    )
    stream = result.stdout.strip() or result.stderr.strip()
    if result.returncode:
        raise WatcherError(f"cannot inspect Herdr agents: {stream}")
    try:
        return json.loads(stream)["result"]["agents"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise WatcherError(f"Herdr returned invalid agent state: {stream}") from error


class HerdrAdapter:
    def prompt_agent(self, agent_name: str, message: str) -> None:
        result = subprocess.run(
            ["herdr", "agent", "prompt", agent_name, message],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            stream = result.stdout.strip() or result.stderr.strip()
            raise WatcherError(f"cannot signal {agent_name}: {stream}")


def _read_state(state_path: Path) -> dict[str, Any]:
    return read_state(state_path)


def _event_id(state: dict[str, Any], event: dict[str, Any]) -> str:
    identity = {
        "run_id": state.get("run_id") or state.get("contract_id"),
        "type": event["type"],
        "lane_id": event.get("lane_id"),
        "generation": event.get("generation"),
        "session_id": event.get("session_id"),
        "pane_id": event.get("pane_id"),
        "status": event.get("status"),
        "reason": event.get("reason"),
        "message": event.get("message"),
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return "evt_" + hashlib.sha256(encoded).hexdigest()[:16]


def _append_events(state_path: Path, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not events:
        return []
    def mutate(state: dict[str, Any]) -> list[dict[str, Any]]:
        queued = state.setdefault("watcher_events", [])
        seen = {event.get("event_id") for event in queued}
        appended = []
        for event in events:
            value = dict(event)
            value["event_id"] = _event_id(state, value)
            if value["event_id"] in seen:
                continue
            queued.append(value)
            seen.add(value["event_id"])
            appended.append(value)
        return appended

    return atomic_update(state_path, mutate)


def reconcile_once(
    state_path: Path,
    live_agents: list[dict[str, Any]],
    missing_checks: int = 3,
) -> list[dict[str, Any]]:
    if missing_checks < 1:
        raise WatcherError("missing_checks must be at least 1")
    state = _read_state(state_path)
    lanes = state.get("lanes", {})
    observations = receipt_reconcile_once(state_path, list(lanes), live_agents)
    events: list[dict[str, Any]] = []

    for lane_id, status in sorted(observations["terminal"].items()):
        lane = lanes[lane_id]
        events.append(
            {
                "type": "RECEIPT",
                "contract_id": state["contract_id"],
                "lane_id": lane_id,
                "generation": lane["generation"],
                "session_id": lane["session_id"],
                "pane_id": lane["pane_id"],
                "status": status,
            }
        )

    for lane_id, moved in sorted(observations["moved"].items()):
        lane = lanes[lane_id]
        events.append(
            {
                "type": "LANE_MOVED",
                "contract_id": state["contract_id"],
                "lane_id": lane_id,
                "generation": lane["generation"],
                "session_id": moved["session_id"],
                "previous_pane_id": moved["previous_pane_id"],
                "pane_id": moved["pane_id"],
            }
        )

    for lane_id, drift in sorted(observations["name_drift"].items()):
        lane = lanes[lane_id]
        events.append(
            {
                "type": "LANE_NAME_DRIFT",
                "contract_id": state["contract_id"],
                "lane_id": lane_id,
                "generation": lane["generation"],
                "session_id": drift["session_id"],
                "pane_id": drift["pane_id"],
                "agent_name": drift["agent_name"],
                "expected_agent_name": drift["expected_agent_name"],
            }
        )

    live_or_terminal = (
        set(observations["terminal"])
        | set(observations["moved"])
        | set(observations["name_drift"])
    )

    def update_missing_counts(value: dict[str, Any]) -> list[dict[str, Any]]:
        current_events: list[dict[str, Any]] = []
        counts = value.setdefault("watcher_missing_counts", {})
        current_lanes = value.get("lanes", {})
        for lane_id in sorted(set(current_lanes) - set(observations["missing"]) - live_or_terminal):
            counts.pop(lane_id, None)
        for lane_id in set(observations["terminal"]) | set(observations["moved"]) | set(observations["name_drift"]):
            counts.pop(lane_id, None)
        for lane_id, lost in sorted(observations["missing"].items()):
            count = int(counts.get(lane_id, 0)) + 1
            counts[lane_id] = count
            if count < missing_checks:
                continue
            lane = current_lanes.get(lane_id, {})
            if lane.get("generation") == lost["generation"]:
                lane["state"] = "SUPERSEDED"
            current_events.append(
                {
                    "type": "LANE_LOST",
                    "contract_id": value["contract_id"],
                    "lane_id": lane_id,
                    "generation": lost["generation"],
                    "session_id": lost["session_id"],
                    "pane_id": lost["pane_id"],
                    "reason": lost["reason"],
                }
            )
        return current_events

    events.extend(atomic_update(state_path, update_missing_counts))
    return _append_events(state_path, events)


def append_watcher_failure(state_path: Path, message: str) -> dict[str, Any]:
    state = _read_state(state_path)
    event = {
        "type": "WATCHER_FAILURE",
        "contract_id": state.get("contract_id"),
        "message": message,
    }
    appended = _append_events(state_path, [event])
    if appended:
        return appended[0]
    event["event_id"] = _event_id(state, event)
    return event


def signal_idle_p1(state_path: Path, event: dict[str, Any], adapter: Any) -> bool:
    state = _read_state(state_path)
    controller = state.get("controller") or state.get("p1") or {}
    if controller.get("status") not in SETTLED_P1_STATUSES:
        return False
    agent_name = controller.get("agent_name")
    if not agent_name:
        return False
    adapter.prompt_agent(agent_name, f"HERDR_EVENT {event['event_id']}")
    return True


def _terminal_lane_ids(state: dict[str, Any]) -> set[str]:
    terminal = set()
    for event in state.get("watcher_events", []):
        if event.get("type") in TERMINAL_EVENT_TYPES and event.get("lane_id"):
            terminal.add(event["lane_id"])
    return terminal


def run_watcher(
    state_path: Path,
    live_agents: Callable[[], list[dict[str, Any]]],
    *,
    adapter: Any | None = None,
    clock: Any | None = None,
    poll: float = 1.0,
    missing_checks: int = 3,
    max_ticks: int | None = None,
) -> dict[str, Any]:
    clock = clock or time
    adapter = adapter or HerdrAdapter()
    ticks = 0
    emitted = 0
    while max_ticks is None or ticks < max_ticks:
        ticks += 1
        try:
            events = reconcile_once(
                state_path,
                live_agents(),
                missing_checks=missing_checks,
            )
        except Exception as error:
            append_watcher_failure(state_path, str(error))
            raise
        emitted += len(events)
        for event in events:
            signal_idle_p1(state_path, event, adapter)
        state = _read_state(state_path)
        if set(state.get("lanes", {})) <= _terminal_lane_ids(state):
            return {"status": "terminal", "ticks": ticks, "events": emitted}
        clock.sleep(poll)
    return {"status": "running", "ticks": ticks, "events": emitted}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-state", type=Path, required=True)
    parser.add_argument("--poll", type=float, default=1.0)
    parser.add_argument("--missing-checks", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_watcher(
            args.control_state,
            live_agents=list_live_agents,
            poll=args.poll,
            missing_checks=args.missing_checks,
        )
    except (OSError, ValueError, WatcherError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
