#!/usr/bin/env python3
"""Start, bind, and reconcile fixed Herdr implementation workers."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from scripts.herdr_identity import agent_identity, fixed_role_name
    from scripts.workspace_state import IMPLEMENTATION_SLOTS, StateError, mutate_state
except ModuleNotFoundError:
    from herdr_identity import agent_identity, fixed_role_name
    from workspace_state import IMPLEMENTATION_SLOTS, StateError, mutate_state


class PoolError(RuntimeError):
    pass


def start_command(slot: str, workspace_id: str, occupied: set[str]) -> list[str]:
    name = fixed_role_name(slot, workspace_id, occupied)
    model = "gpt-5.6-sol" if slot == "P1" else "gpt-5.5"
    effort = "xhigh" if slot == "P1" else "high"
    return [
        "herdr", "agent", "start", "--name", name,
        "--", "codex", "--yolo", "-m", model,
        "-c", f"model_reasoning_effort={effort}",
    ]


class WorkerPool:
    def __init__(self, client: Any, state_path: Path, workspace_id: str):
        self.client = client
        self.state_path = Path(state_path)
        self.workspace_id = workspace_id

    def ensure(self, slots: list[str]) -> dict:
        observations = [agent_identity(item) for item in self.client.list_agents()]
        occupied = {item["name"] for item in observations if item.get("name")}
        for slot in slots:
            if slot not in IMPLEMENTATION_SLOTS:
                raise PoolError(f"unsupported worker slot: {slot}")
            if not self._local_slot_live(slot, observations):
                self._start(slot, occupied)
                occupied.add(self._slot_role_name(slot))
        return self.reconcile(observations)

    def reconcile(
        self,
        live: list[dict] | None = None,
        *,
        restart_detected: bool = False,
    ) -> dict:
        observations = live or [
            agent_identity(item) for item in self.client.list_agents()
        ]
        return apply_pool_observations(
            self.state_path,
            self.workspace_id,
            observations,
            self._start,
            restart_detected=restart_detected,
        )

    def _local_slot_live(self, slot: str, observations: list[dict]) -> bool:
        local = [
            item for item in observations
            if item.get("workspace_id") == self.workspace_id
        ]
        state = _load_without_mutating(self.state_path)
        stored = state["slots"][slot]
        session = stored.get("session_id")
        if session:
            return any(item.get("session_id") == session for item in local)
        if stored.get("status") == "STARTING":
            return True
        role_name = stored.get("role_name") or fixed_role_name(
            slot,
            self.workspace_id,
            {item["name"] for item in local if item.get("name")},
        )
        return any(
            item.get("name") == role_name and item.get("session_id")
            for item in local
        )

    def _slot_role_name(self, slot: str) -> str:
        state = _load_without_mutating(self.state_path)
        return state["slots"][slot].get("role_name") or fixed_role_name(
            slot, self.workspace_id, set()
        )

    def _start(self, slot: str, occupied: set[str] | None = None) -> None:
        occupied = occupied or set()
        command = start_command(slot, self.workspace_id, occupied)
        role_name = command[4]

        def mark_starting(value: dict) -> None:
            value["slots"][slot].update(
                {
                    "role_name": role_name,
                    "session_id": None,
                    "pane_id": None,
                    "workspace_id": self.workspace_id,
                    "terminal_id": None,
                    "status": "STARTING",
                    "misses": 0,
                }
            )

        mutate_state(self.state_path, mark_starting)
        try:
            self.client.start_agent(command, slot)
        except Exception as error:
            def mark_failed(value: dict) -> None:
                value["slots"][slot]["status"] = "START_FAILED"
                value["slots"][slot]["error"] = str(error)

            mutate_state(self.state_path, mark_failed)
            raise


def apply_pool_observations(
    state_path: Path,
    workspace_id: str,
    observations: list[dict],
    start_slot,
    *,
    restart_detected: bool = False,
) -> dict:
    local = [
        item for item in observations
        if item.get("workspace_id") == workspace_id
    ]
    by_session = {
        item["session_id"]: item
        for item in local
        if item.get("session_id")
    }
    by_name = {
        item["name"]: item
        for item in local
        if item.get("name")
    }
    replacements: list[str] = []

    def mutate(value: dict) -> dict:
        if restart_detected:
            _clear_restart_bindings(value)
            return value

        for slot in IMPLEMENTATION_SLOTS:
            record = value["slots"][slot]
            session = record.get("session_id")
            if session:
                agent = by_session.get(session)
                if agent:
                    _bind_slot(record, agent, workspace_id)
                    continue
                _record_miss_or_replacement(value, slot, replacements)
                continue

            role_name = record.get("role_name")
            agent = by_name.get(role_name) if role_name else None
            if agent and agent.get("session_id"):
                _bind_slot(record, agent, workspace_id)

        return value

    result = mutate_state(state_path, mutate)
    occupied = {item["name"] for item in observations if item.get("name")}
    for slot in replacements:
        start_slot(slot, occupied)
        occupied.add(fixed_role_name(slot, workspace_id, occupied))
    return result


def _clear_restart_bindings(value: dict) -> None:
    value.setdefault("run", {})["controller_session_id"] = None
    value["run"]["pool_restart_epoch"] = time.monotonic_ns()
    for slot in IMPLEMENTATION_SLOTS:
        record = value["slots"][slot]
        lane = value["lanes"].get(record.get("lane_id"))
        if lane and (lane.get("output_artifact") or _receipt_exists(lane)):
            lane["artifact_state"] = "REUSABLE"
        record.update(
            {
                "session_id": None,
                "pane_id": None,
                "terminal_id": None,
                "status": "COLD",
                "misses": 0,
            }
        )


def _bind_slot(record: dict, agent: dict, workspace_id: str) -> None:
    record.update(
        {
            "session_id": agent.get("session_id"),
            "pane_id": agent.get("pane_id"),
            "workspace_id": workspace_id,
            "terminal_id": agent.get("terminal_id"),
            "status": (agent.get("status") or "live").upper(),
            "misses": 0,
        }
    )


def _record_miss_or_replacement(
    value: dict,
    slot: str,
    replacements: list[str],
) -> None:
    record = value["slots"][slot]
    lane = value["lanes"].get(record.get("lane_id"))
    if lane and _valid_receipt_for_lane(lane):
        lane["state"] = "ACCEPTED"
        record.update(
            {
                "session_id": None,
                "pane_id": None,
                "terminal_id": None,
                "status": "DONE",
                "misses": 0,
            }
        )
        return

    record["misses"] = int(record.get("misses", 0)) + 1
    if record["misses"] < 3:
        return

    if lane:
        lane["state"] = "SUPERSEDED"
    record.pop("lane_id", None)
    record.pop("generation", None)
    record.update(
        {
            "session_id": None,
            "pane_id": None,
            "terminal_id": None,
            "status": "COLD",
            "misses": 0,
        }
    )
    replacements.append(slot)


def _valid_receipt_for_lane(lane: dict) -> bool:
    path = Path(lane.get("receipt_path", ""))
    if not _receipt_exists(lane):
        return False
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        receipt.get("status") == "PASS"
        and receipt.get("lane_id") == lane.get("lane_id")
        and receipt.get("generation") == lane.get("generation")
        and receipt.get("session_id") == lane.get("session_id")
    )


def _receipt_exists(lane: dict) -> bool:
    receipt_path = lane.get("receipt_path")
    return bool(receipt_path and Path(receipt_path).is_file())


def _load_without_mutating(path: Path) -> dict:
    try:
        from scripts.workspace_state import load_state
    except ModuleNotFoundError:
        from workspace_state import load_state

    return load_state(path)


class HerdrClient:
    def list_agents(self) -> list[dict]:
        return self._run(["agent", "list"])["result"]["agents"]

    def start_agent(self, command: list[str], slot: str) -> None:
        del slot
        self._run(command[1:])

    @staticmethod
    def _run(args: list[str]) -> dict:
        result = subprocess.run(
            ["herdr", *args],
            check=False,
            capture_output=True,
            text=True,
        )
        stream = result.stdout.strip() or result.stderr.strip()
        try:
            payload = json.loads(stream)
        except json.JSONDecodeError as error:
            raise PoolError(f"Herdr returned non-JSON output: {stream}") from error
        if result.returncode:
            message = payload.get("error", payload)
            raise PoolError(json.dumps(message, sort_keys=True))
        return payload


def default_state_path(workspace_id: str) -> Path:
    return Path.home() / ".codex" / "herdr-runs" / workspace_id / "workspace-state.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--workspace", default="")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ensure = subparsers.add_parser("ensure")
    ensure.add_argument("--slot", action="append", required=True)

    reconcile = subparsers.add_parser("reconcile")
    reconcile.add_argument("--restart-detected", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace_id = args.workspace or "default"
    state_path = args.state_file or default_state_path(workspace_id)
    pool = WorkerPool(HerdrClient(), state_path, workspace_id)
    try:
        if args.command == "ensure":
            result = pool.ensure(args.slot)
        else:
            result = pool.reconcile(restart_detected=args.restart_detected)
    except (PoolError, StateError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 1
    print(json.dumps({"status": "ok", "state": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
