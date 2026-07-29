#!/usr/bin/env python3
"""Pure Herdr controller identity decisions and safe P1 request forwarding."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any


SETTLED_STATUSES = {"idle", "done"}
WORKER_NAMES = {f"hdr_p{index}" for index in range(2, 10)}


class RouterError(RuntimeError):
    pass


def session_id(agent: dict[str, Any]) -> str | None:
    session = agent.get("agent_session") or {}
    value = session.get("value")
    return str(value) if value else None


def compact_identity(agent: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": agent.get("name") or "",
        "pane_id": agent.get("pane_id"),
        "workspace_id": agent.get("workspace_id"),
        "terminal_id": agent.get("terminal_id"),
        "session_id": session_id(agent),
        "status": agent.get("agent_status"),
    }


def decide_controller_action(
    current_agent: dict[str, Any],
    live_controller: dict[str, Any] | None,
) -> dict[str, Any]:
    current = compact_identity(current_agent)
    current_name = current["name"]

    if current_name == "hdr_p1":
        if not live_controller:
            return {"action": "CONTINUE", **current}
        controller = compact_identity(live_controller)
        if controller["session_id"] != current["session_id"]:
            return {
                "action": "BLOCK",
                "reason": "BLOCKED_ROLE_CONFLICT",
            }
        return {"action": "CONTINUE", **current}

    if current_name in WORKER_NAMES:
        if not live_controller:
            return {
                "action": "BLOCK",
                "reason": "BLOCKED_NO_CONTROLLER",
            }
        controller = compact_identity(live_controller)
        return {
            "action": "FORWARD",
            "controller_session_id": controller["session_id"],
            "controller_pane_id": controller["pane_id"],
        }

    if live_controller:
        return {
            "action": "BLOCK",
            "reason": "BLOCKED_ROLE_CONFLICT",
        }

    if current_name:
        return {
            "action": "BLOCK",
            "reason": "BLOCKED_NO_CONTROLLER",
        }

    return {"action": "PROMOTE", **current}


class ControllerRouter:
    def __init__(self, client: Any, inbox_root: Path, socket_key: str):
        self.client = client
        self.inbox_root = Path(inbox_root)
        self.socket_key = socket_key

    def promote(self, current_agent: dict[str, Any]) -> dict[str, Any]:
        before = compact_identity(current_agent)
        if before["name"]:
            raise RouterError("only unnamed agents can promote")
        if not before["session_id"]:
            raise RouterError("session identity is unavailable")
        self.client.rename_agent(before["pane_id"], "hdr_p1")

        live = [
            compact_identity(agent)
            for agent in self.client.list_agents()
            if agent.get("name") == "hdr_p1"
        ]
        controller = next(
            (
                agent
                for agent in live
                if agent["pane_id"] == before["pane_id"]
                and agent["terminal_id"] == before["terminal_id"]
            ),
            None,
        )
        if not controller:
            raise RouterError("controller identity changed during promotion")
        if controller["session_id"] != before["session_id"]:
            raise RouterError("session identity changed during promotion")
        return {"action": "PROMOTE", "controller": controller}

    def forward_request(
        self,
        current_agent: dict[str, Any],
        controller: dict[str, Any],
        request: dict[str, Any],
    ) -> dict[str, Any]:
        current = compact_identity(current_agent)
        target = compact_identity(controller)
        envelope = {
            "schema_version": "herdr-p1-request/v1",
            "socket_key": self.socket_key,
            "from": current,
            "controller": target,
            "request": request,
        }
        request_id = deterministic_request_id(envelope)
        inbox = self.inbox_root / self.socket_key / "p1-inbox"
        path = inbox / f"{request_id}.json"
        with locked(inbox):
            already_queued = path.exists()
            if not already_queued:
                atomic_json_write(path, envelope)

        if target["status"] in SETTLED_STATUSES and not already_queued:
            self.client.signal_agent("hdr_p1", request_id)
            return {"action": "FORWARDED", "request_id": request_id}
        return {"action": "QUEUED", "request_id": request_id}


def deterministic_request_id(envelope: dict[str, Any]) -> str:
    encoded = json.dumps(
        request_id_identity(envelope),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()[:24]


def request_id_identity(envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": envelope["schema_version"],
        "socket_key": envelope["socket_key"],
        "from": immutable_agent_identity(envelope["from"]),
        "controller": immutable_agent_identity(envelope["controller"]),
        "request": envelope["request"],
    }


def immutable_agent_identity(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        key: identity.get(key)
        for key in (
            "name",
            "pane_id",
            "workspace_id",
            "terminal_id",
            "session_id",
        )
    }


@contextmanager
def locked(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    lock_path = directory / ".lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def atomic_json_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(encoded)
    temporary.replace(path)
