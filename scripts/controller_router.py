#!/usr/bin/env python3
"""Pure Herdr controller identity decisions and safe P1 request forwarding."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:
    from scripts.agent_naming import (
        format_agent_name,
        slot_from_agent_name,
        stable_agent_identity,
    )
    from scripts.runtime_registry import RuntimeRegistry
except ModuleNotFoundError:
    from agent_naming import (
        format_agent_name,
        slot_from_agent_name,
        stable_agent_identity,
    )
    from runtime_registry import RuntimeRegistry


SETTLED_STATUSES = {"idle", "done"}
WORKER_SLOTS = {f"P{index}" for index in range(2, 10)}


class RouterError(RuntimeError):
    pass


def session_id(agent: dict[str, Any]) -> str | None:
    if agent.get("session_id"):
        return str(agent["session_id"])
    session = agent.get("agent_session") or {}
    value = session.get("value")
    return str(value) if value else None


def compact_identity(agent: dict[str, Any]) -> dict[str, Any]:
    session = session_id(agent)
    return {
        "name": agent.get("name") or "",
        "pane_id": agent.get("pane_id"),
        "workspace_id": agent.get("workspace_id"),
        "terminal_id": agent.get("terminal_id"),
        "session_id": session,
        "status": agent.get("agent_status"),
    }


def controller_scope_id(session: str) -> str:
    return hashlib.sha256(session.encode()).hexdigest()[:8]


def controller_name(scope: str, occupied: set[str]) -> str:
    return format_agent_name(
        "P1",
        "orchestrator",
        occupied=occupied,
        collision_key=scope,
    )


def decide_controller_action(
    current_agent: dict[str, Any],
    live_controller: dict[str, Any] | None,
) -> dict[str, Any]:
    current = compact_identity(current_agent)
    current_name = current["name"]
    current_slot = slot_from_agent_name(current_name)

    if current_slot == "P1":
        if not live_controller:
            return {"action": "CONTINUE", **current}
        controller = compact_identity(live_controller)
        if controller["session_id"] != current["session_id"]:
            return {
                "action": "BLOCK",
                "reason": "BLOCKED_ROLE_CONFLICT",
            }
        return {"action": "CONTINUE", **current}

    if current_slot in WORKER_SLOTS:
        if not live_controller:
            return {
                "action": "BLOCK",
                "reason": "BLOCKED_NO_CONTROLLER",
            }
        controller = compact_identity(live_controller)
        if _workspace_mismatch(current, controller):
            return {
                "action": "BLOCK",
                "reason": "BLOCKED_WORKSPACE_MISMATCH",
            }
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
        self.registry = RuntimeRegistry(self.inbox_root, socket_key)

    def promote(self, current_agent: dict[str, Any]) -> dict[str, Any]:
        before = compact_identity(current_agent)
        if before["name"]:
            raise RouterError("only unnamed agents can promote")
        if not before["session_id"]:
            raise RouterError("session identity is unavailable")
        scope = controller_scope_id(before["session_id"])
        token = f"controller:{scope}:{before['session_id']}"
        reservation = self.registry.reserve_visible_name(
            controller_scope=scope,
            slot="P1",
            role="orchestrator",
            reservation_token=token,
            live_names={agent.get("name") for agent in self.client.list_agents()},
        )
        self.client.rename_agent(before["pane_id"], reservation["name"])

        live = [
            compact_identity(agent)
            for agent in self.client.list_agents()
            if session_id(agent) == before["session_id"]
        ]
        if len(live) != 1:
            changed_session = [
                compact_identity(agent)
                for agent in self.client.list_agents()
                if agent.get("pane_id") == before["pane_id"]
                and agent.get("terminal_id") == before["terminal_id"]
            ]
            if changed_session:
                raise RouterError("session identity changed during promotion")
            raise RouterError("controller identity changed during promotion")
        controller = live[0]
        if (
            controller["pane_id"] != before["pane_id"]
            or controller["terminal_id"] != before["terminal_id"]
        ):
            raise RouterError("controller identity changed during promotion")
        if controller["session_id"] != before["session_id"]:
            raise RouterError("session identity changed during promotion")
        self.registry.finalize_visible_name(
            controller_scope=scope,
            reservation_token=token,
            session_id=before["session_id"],
            name=reservation["name"],
        )
        controller["controller_scope"] = scope
        self._ensure_scoped_inbox(scope)
        return {"action": "PROMOTE", "controller": controller}

    def ensure_controller_name(
        self,
        current_agent: dict[str, Any],
        *,
        controller_scope: str | None = None,
    ) -> dict[str, Any]:
        before = compact_identity(current_agent)
        if slot_from_agent_name(before["name"]) != "P1":
            raise RouterError("current agent is not the controller")
        if not before["session_id"]:
            raise RouterError("session identity is unavailable")
        scope = controller_scope or controller_scope_id(before["session_id"])
        token = f"controller:{scope}:{before['session_id']}"
        registered = self.registry.read()["controller_scopes"].get(scope)
        if registered:
            expected_name = registered["name"]
        else:
            reservation = self.registry.reserve_visible_name(
                controller_scope=scope,
                slot="P1",
                role="orchestrator",
                reservation_token=token,
                live_names={
                    agent.get("name")
                    for agent in self.client.list_agents()
                    if session_id(agent) != before["session_id"]
                },
            )
            expected_name = reservation["name"]
        if before["name"] != expected_name:
            if before["name"] != "hdr_p1" and not registered:
                raise RouterError("unsupported controller display name")
            self.client.rename_agent(before["pane_id"], expected_name)
        matches = [
            compact_identity(agent)
            for agent in self.client.list_agents()
            if session_id(agent) == before["session_id"]
        ]
        if len(matches) != 1 or matches[0]["name"] != expected_name:
            raise RouterError("controller rename was not verified")
        after = matches[0]
        if after["terminal_id"] != before["terminal_id"]:
            raise RouterError("controller terminal changed during migration")
        if not registered:
            self.registry.finalize_visible_name(
                controller_scope=scope,
                reservation_token=token,
                session_id=before["session_id"],
                name=expected_name,
            )
        after["controller_scope"] = scope
        self._ensure_scoped_inbox(scope)
        self._migrate_legacy_inbox(scope, before["session_id"])
        return after

    def forward_request(
        self,
        current_agent: dict[str, Any],
        controller: dict[str, Any],
        request: dict[str, Any],
    ) -> dict[str, Any]:
        current = compact_identity(current_agent)
        target = compact_identity(controller)
        if _workspace_mismatch(current, target):
            raise RouterError("workspace mismatch")
        scope = (
            controller.get("controller_scope")
            or controller_scope_id(target["session_id"])
        )
        target["controller_scope"] = scope
        envelope = {
            "schema_version": "herdr-p1-request/v1",
            "socket_key": self.socket_key,
            "controller_scope": scope,
            "from": current,
            "controller": target,
            "request": request,
        }
        request_id = deterministic_request_id(envelope)
        inbox = self._ensure_scoped_inbox(scope)
        path = inbox / f"{request_id}.json"
        with locked(inbox):
            already_queued = path.exists()
            if not already_queued:
                atomic_json_write(path, envelope)

        if target["status"] in SETTLED_STATUSES and not already_queued:
            self.client.signal_agent(target["name"], request_id)
            return {"action": "FORWARDED", "request_id": request_id}
        return {"action": "QUEUED", "request_id": request_id}

    def _ensure_scoped_inbox(self, scope: str) -> Path:
        inbox = self.inbox_root / self.socket_key / scope / "p1-inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        return inbox

    def _migrate_legacy_inbox(self, scope: str, session: str) -> None:
        legacy = self.inbox_root / self.socket_key / "p1-inbox"
        if not legacy.exists():
            return
        target = self._ensure_scoped_inbox(scope)
        marker = target / ".legacy-migrated"
        if marker.exists():
            return
        self.registry.claim_legacy_resources(
            controller_scope=scope,
            session_id=session,
        )
        with locked(target):
            for path in legacy.iterdir():
                if not path.is_file() or path.name == ".lock":
                    continue
                destination = target / path.name
                if not destination.exists():
                    path.replace(destination)
                else:
                    path.unlink()
            marker.write_text("ok\n", encoding="utf-8")
            try:
                legacy.rmdir()
            except OSError:
                shutil.rmtree(legacy, ignore_errors=True)


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
        "controller_scope": envelope["controller_scope"],
        "from": immutable_agent_identity(envelope["from"]),
        "controller": immutable_agent_identity(envelope["controller"]),
        "request": envelope["request"],
    }


def immutable_agent_identity(identity: dict[str, Any]) -> dict[str, Any]:
    return stable_agent_identity(
        identity.get("name"),
        identity.get("session_id"),
    )


def _workspace_mismatch(
    current: dict[str, Any],
    controller: dict[str, Any],
) -> bool:
    current_workspace = current.get("workspace_id")
    controller_workspace = controller.get("workspace_id")
    return bool(
        current_workspace
        and controller_workspace
        and current_workspace != controller_workspace
    )


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
