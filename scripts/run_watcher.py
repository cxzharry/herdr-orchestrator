#!/usr/bin/env python3
"""Observe one Herdr workspace and wake P1 after events are persisted."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.herdr_identity import agent_identity
    from scripts.workspace_state import load_state, mutate_state
except ModuleNotFoundError:
    from herdr_identity import agent_identity
    from workspace_state import load_state, mutate_state


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
    def list_agents(self) -> list[dict[str, Any]]:
        return list_live_agents()

    def signal_agent(self, agent_name: str, message: str) -> None:
        result = subprocess.run(
            ["herdr", "agent", "prompt", agent_name, message],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            stream = result.stdout.strip() or result.stderr.strip()
            raise WatcherError(f"cannot signal {agent_name}: {stream}")


def acquire_watcher(
    state_path: Path,
    watcher_id: str,
    *,
    controller_session: str,
) -> bool:
    def mutate(state: dict[str, Any]) -> bool:
        controller = state.get("controller", {})
        if controller.get("session_id") != controller_session:
            raise WatcherError("controller session does not match workspace state")
        watcher = state.setdefault("watcher", {})
        existing = watcher.get("watcher_id")
        if existing and existing != watcher_id:
            return False
        watcher["watcher_id"] = watcher_id
        return True

    return bool(mutate_state(state_path, mutate))


def observe_once(
    state: dict[str, Any],
    live_agents: list[dict[str, Any]],
    receipt_paths: dict[str, str] | None,
    now: int | float,
) -> dict[str, Any]:
    live_sessions = {
        identity["session_id"]
        for identity in (agent_identity(agent) for agent in live_agents)
        if identity.get("session_id")
    }
    events = []
    for lane_id, lane in sorted(state.get("lanes", {}).items()):
        if lane.get("state") != "ACTIVE":
            continue
        session_id = lane.get("session_id")
        if session_id and session_id not in live_sessions:
            events.append(
                {
                    "kind": "LANE_MISSING",
                    "lane_id": lane_id,
                    "generation": lane.get("generation"),
                    "session_id": session_id,
                    "artifact": None,
                }
            )
    for lane_id, receipt_path in sorted((receipt_paths or {}).items()):
        path = Path(receipt_path)
        if path.exists():
            events.append(
                {
                    "kind": "RECEIPT_PRESENT",
                    "lane_id": lane_id,
                    "generation": state["lanes"][lane_id].get("generation"),
                    "session_id": state["lanes"][lane_id].get("session_id"),
                    "artifact": str(path),
                }
            )
    return {"heartbeat_at": now, "events": events}


def expected_receipt_paths(state: dict[str, Any]) -> dict[str, str]:
    return {
        lane_id: lane["receipt_path"]
        for lane_id, lane in state.get("lanes", {}).items()
        if lane.get("receipt_path")
    }


def record_heartbeat(state_path: Path, now: int | float) -> None:
    def mutate(state: dict[str, Any]) -> None:
        state.setdefault("watcher", {})["heartbeat_at"] = now

    mutate_state(state_path, mutate)


def run_once(state_path: Path, adapter: Any, now: int | float) -> dict[str, Any]:
    state = load_state(state_path)
    observation = observe_once(
        state,
        adapter.list_agents(),
        expected_receipt_paths(state),
        now,
    )
    persisted = [_append_unique_workspace_event(state_path, event) for event in observation["events"]]
    record_heartbeat(state_path, now)
    if persisted:
        adapter.signal_agent(state["controller"]["role_name"], "HERDR_EVENT")
    return observation


def verify_wake_path(
    state_path: Path,
    adapter: Any,
    now: int | float,
    *,
    advanced_cursor: Callable[[], int],
) -> bool:
    before = load_state(state_path).get("event_cursor", 0)
    _append_unique_workspace_event(
        state_path,
        {
            "kind": "WAKE_PROBE",
            "lane_id": None,
            "generation": None,
            "session_id": None,
            "artifact": None,
        },
    )
    state = load_state(state_path)
    adapter.signal_agent(state["controller"]["role_name"], "HERDR_WAKE_PROBE")
    verified = advanced_cursor() > before

    def mutate(value: dict[str, Any]) -> None:
        value.setdefault("watcher", {})["heartbeat_at"] = now
        if verified:
            value["watcher"]["wake_verified_at"] = now

    mutate_state(state_path, mutate)
    return verified


def run_watcher(
    state_path: Path,
    *,
    adapter: Any | None = None,
    clock: Any | None = None,
    poll: float = 1.0,
    max_ticks: int | None = None,
) -> dict[str, Any]:
    clock = clock or time
    adapter = adapter or HerdrAdapter()
    ticks = 0
    emitted = 0
    while max_ticks is None or ticks < max_ticks:
        ticks += 1
        result = run_once(state_path, adapter, now=clock.monotonic())
        emitted += len(result["events"])
        clock.sleep(poll)
    return {"status": "running", "ticks": ticks, "events": emitted}


def _append_unique_workspace_event(state_path: Path, event: dict[str, Any]) -> dict[str, Any] | None:
    def mutate(state: dict[str, Any]) -> dict[str, Any] | None:
        value = dict(event)
        value["event_id"] = _workspace_event_id(state, value)
        existing = {
            item.get("event_id")
            for item in state.setdefault("events", [])
            if item.get("event_id")
        }
        if value["event_id"] in existing:
            return None
        state["event_cursor"] = int(state.get("event_cursor", 0)) + 1
        state["events"].append({"cursor": state["event_cursor"], **value})
        return value

    return mutate_state(state_path, mutate)


def _workspace_event_id(state: dict[str, Any], event: dict[str, Any]) -> str:
    identity = {
        "workspace_id": state.get("workspace_id"),
        "kind": event.get("kind"),
        "lane_id": event.get("lane_id"),
        "generation": event.get("generation"),
        "session_id": event.get("session_id"),
        "artifact": event.get("artifact"),
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return "evt_" + hashlib.sha256(encoded).hexdigest()[:16]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-state", type=Path, required=True)
    parser.add_argument("--poll", type=float, default=1.0)
    parser.add_argument("--max-ticks", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_watcher(
            args.control_state,
            poll=args.poll,
            max_ticks=args.max_ticks,
        )
    except (OSError, ValueError, WatcherError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
