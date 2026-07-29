#!/usr/bin/env python3
"""Rename one live Herdr lane from approved display metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

try:
    from scripts.agent_naming import format_agent_name
    from scripts.runtime_registry import RegistryError, RuntimeRegistry
    from scripts.scheduler_state import atomic_update, read_state
except ModuleNotFoundError:
    from agent_naming import format_agent_name
    from runtime_registry import RegistryError, RuntimeRegistry
    from scheduler_state import atomic_update, read_state


class AssignmentError(RuntimeError):
    pass


def _session_id(agent: dict[str, Any]) -> str | None:
    value = (agent.get("agent_session") or {}).get("value")
    return str(value) if value else None


def _reservation_token(state: dict[str, Any], lane_id: str, lane: dict[str, Any], expected: str) -> str:
    token_source = "|".join(
        [
            state["controller_scope"],
            state["contract_id"],
            lane_id,
            str(lane["generation"]),
            str(lane.get("session_id")),
            expected,
        ]
    )
    return hashlib.sha256(token_source.encode()).hexdigest()[:24]


def clear_name_reservation(state_path: Path, lane_id: str, token: str) -> None:
    def clear(value: dict[str, Any]) -> dict[str, Any] | None:
        lane = value.get("lanes", {}).get(lane_id)
        if not lane:
            return None
        reservation = lane.get("name_assignment") or {}
        if reservation.get("token") == token:
            lane.pop("name_assignment", None)
        return None

    atomic_update(state_path, clear)


def assign_lane_name(
    state_path: Path,
    lane_id: str,
    client: Any,
    *,
    expected_generation: int | None = None,
    record_dispatch: bool = True,
    registry: Any | None = None,
) -> dict[str, Any]:
    state = read_state(state_path)
    lane = state.get("lanes", {}).get(lane_id)
    if lane is None:
        raise AssignmentError(f"unknown lane: {lane_id}")
    generation = int(lane["generation"])
    if expected_generation is not None and generation != expected_generation:
        raise AssignmentError("lane generation changed before rename")
    session = lane.get("session_id")
    slot = lane.get("slot")
    if not slot:
        raise AssignmentError("lane has no P1-P9 slot")
    agents = client.list_agents()
    live = [agent for agent in agents if _session_id(agent) == session]
    if len(live) != 1:
        raise AssignmentError("lane session is not uniquely live")
    occupied = {
        agent.get("name")
        for agent in agents
        if _session_id(agent) != session and agent.get("name")
    }
    task = lane.get("display_slug") if "display_slug" in lane else lane_id
    expected = format_agent_name(
        slot,
        lane["display_role"],
        task,
        occupied=occupied,
        collision_key=f"{state['controller_scope']}:{lane_id}",
    )
    token = _reservation_token(state, lane_id, lane, expected)

    def reserve(value: dict[str, Any]) -> dict[str, Any]:
        current = value["lanes"].get(lane_id)
        if (
            current is None
            or int(current["generation"]) != generation
            or current.get("session_id") != session
        ):
            raise AssignmentError("lane identity changed before reservation")
        reservation = current.get("name_assignment")
        if reservation and reservation.get("token") != token:
            raise AssignmentError("another name assignment is pending")
        current["name_assignment"] = {
            "token": token,
            "generation": generation,
            "session_id": session,
            "expected_agent_name": expected,
        }
        return dict(current)

    atomic_update(state_path, reserve)
    registry_record = None
    try:
        if registry is not None:
            try:
                registry_record = registry.reserve_visible_name(
                    controller_scope=state["controller_scope"],
                    slot=slot,
                    role=lane["display_role"],
                    task=task,
                    reservation_token=token,
                    live_names=occupied,
                )
                if registry_record["name"] != expected:
                    expected = registry_record["name"]
            except RegistryError as error:
                message = str(error)
                if "already leased" in message:
                    message = "session leased to another controller scope"
                raise AssignmentError(message) from error

        agent = live[0]
        if agent.get("name") != expected:
            client.rename_agent(agent["pane_id"], expected)
        verified = [
            value
            for value in client.list_agents()
            if _session_id(value) == session and value.get("name") == expected
        ]
        if len(verified) != 1:
            raise AssignmentError("renamed lane identity was not verified")
        verified_agent = verified[0]

        if registry is not None:
            try:
                registry.finalize_visible_name(
                    controller_scope=state["controller_scope"],
                    reservation_token=token,
                    session_id=str(session),
                    name=expected,
                )
                registry.lease_session(
                    session_id=str(session),
                    controller_scope=state["controller_scope"],
                    contract_id=state["contract_id"],
                    lane_id=lane_id,
                    generation=str(generation),
                )
            except RegistryError as error:
                message = str(error)
                if "already leased" in message:
                    message = "session leased to another controller scope"
                raise AssignmentError(message) from error

        def publish(value: dict[str, Any]) -> dict[str, Any]:
            current = value["lanes"].get(lane_id)
            reservation = (current or {}).get("name_assignment") or {}
            if reservation.get("token") != token:
                raise AssignmentError("name reservation changed")
            current["agent_name"] = expected
            current["expected_agent_name"] = expected
            if record_dispatch:
                current["dispatch_agent_name"] = expected
            current["pane_id"] = verified_agent["pane_id"]
            current.pop("name_assignment", None)
            return dict(current)

        return atomic_update(state_path, publish)
    except Exception:
        if registry is not None and registry_record is not None:
            try:
                registry.release_visible_name(
                    controller_scope=state["controller_scope"],
                    session_id=session,
                    name=expected,
                )
            except RegistryError:
                pass
        clear_name_reservation(state_path, lane_id, token)
        raise


def migrate_legacy_lane_names(
    state_path: Path,
    client: Any,
) -> list[dict[str, Any]]:
    state = read_state(state_path)
    migrated = []
    for lane_id, lane in sorted(state["lanes"].items()):
        if str(lane.get("agent_name", "")).startswith("hdr_p"):
            migrated.append(
                assign_lane_name(
                    state_path,
                    lane_id,
                    client,
                    expected_generation=int(lane["generation"]),
                    record_dispatch=False,
                )
            )
    return migrated


class HerdrNamingClient:
    def _run(self, args: list[str]) -> dict[str, Any]:
        result = subprocess.run(
            ["herdr", *args],
            check=False,
            capture_output=True,
            text=True,
        )
        stream = result.stdout.strip() or result.stderr.strip()
        if result.returncode:
            raise AssignmentError(stream)
        return json.loads(stream)

    def list_agents(self) -> list[dict[str, Any]]:
        return self._run(["agent", "list"])["result"]["agents"]

    def rename_agent(self, pane_id: str, name: str) -> None:
        self._run(["agent", "rename", pane_id, name])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-state", type=Path, required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--lane")
    target.add_argument("--migrate-legacy", action="store_true")
    parser.add_argument("--generation", type=int)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--socket-key")
    args = parser.parse_args()
    try:
        client = HerdrNamingClient()
        registry = (
            RuntimeRegistry(args.runtime_root, args.socket_key)
            if args.runtime_root and args.socket_key
            else None
        )
        result = (
            migrate_legacy_lane_names(args.control_state, client)
            if args.migrate_legacy
            else assign_lane_name(
                args.control_state,
                args.lane,
                client,
                expected_generation=args.generation,
                registry=registry,
            )
        )
    except (OSError, ValueError, AssignmentError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 1
    print(json.dumps({"status": "assigned", "lane": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
