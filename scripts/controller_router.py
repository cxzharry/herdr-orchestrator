#!/usr/bin/env python3
"""Pure Herdr controller identity decisions and same-ledger request forwarding."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from scripts.herdr_identity import ROLE_NAMES, agent_identity
    from scripts.workspace_state import load_state, mutate_state
except ModuleNotFoundError:
    from herdr_identity import ROLE_NAMES, agent_identity
    from workspace_state import load_state, mutate_state


SETTLED_STATUSES = {"idle", "done", "IDLE", "DONE"}
P1_NAME = ROLE_NAMES["P1"]
WORKER_NAMES = {ROLE_NAMES[f"P{index}"] for index in range(2, 10)}


class RouterError(RuntimeError):
    pass


def decide_controller_action(
    current_agent: dict[str, Any],
    live_controller: dict[str, Any] | None,
    *,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    current = agent_identity(current_agent)
    current_workspace = workspace_id or current.get("workspace_id")

    if current["name"] == P1_NAME:
        if not live_controller:
            return {"action": "CONTINUE", "workspace_id": current_workspace, **current}
        controller = agent_identity(live_controller)
        if controller.get("workspace_id") != current_workspace:
            return {"action": "BLOCK", "reason": "BLOCKED_NO_LOCAL_CONTROLLER"}
        if controller["session_id"] != current["session_id"]:
            return {"action": "BLOCK", "reason": "BLOCKED_ROLE_CONFLICT"}
        return {"action": "CONTINUE", "workspace_id": current_workspace, **current}

    if current["name"] in WORKER_NAMES:
        controller = agent_identity(live_controller) if live_controller else None
        if not controller or controller.get("workspace_id") != current_workspace:
            return {"action": "BLOCK", "reason": "BLOCKED_NO_LOCAL_CONTROLLER"}
        return {"action": "FORWARD", "workspace_id": current_workspace}

    if live_controller:
        controller = agent_identity(live_controller)
        if controller.get("workspace_id") != current_workspace:
            return {"action": "BLOCK", "reason": "BLOCKED_NO_LOCAL_CONTROLLER"}
        return {"action": "BLOCK", "reason": "BLOCKED_ROLE_CONFLICT"}

    if current["name"]:
        return {"action": "BLOCK", "reason": "BLOCKED_NO_LOCAL_CONTROLLER"}
    return {"action": "CLAIM_P1", "workspace_id": current_workspace, **current}


class ControllerRouter:
    def __init__(self, client: Any, state_path: Path, workspace_id: str):
        self.client = client
        self.state_path = Path(state_path)
        self.workspace_id = workspace_id

    def claim_p1(self, current_agent: dict[str, Any]) -> dict[str, Any]:
        current = agent_identity(current_agent)
        if current["name"]:
            raise RouterError("only unnamed agents can claim P1")
        if not current["session_id"]:
            raise RouterError("session identity is unavailable")
        if hasattr(self.client, "rename_agent"):
            self.client.rename_agent(current["pane_id"], P1_NAME)

        controller = {**current, "name": P1_NAME, "role_name": P1_NAME}

        def mutate(state: dict[str, Any]) -> dict[str, Any]:
            if state.get("workspace_id") != self.workspace_id:
                raise RouterError("workspace does not match state")
            existing = state.get("controller") or {}
            if existing.get("session_id") not in (None, current["session_id"]):
                raise RouterError("controller session conflict")
            state["controller"] = controller
            return dict(controller)

        return {"action": "CLAIM_P1", "controller": mutate_state(self.state_path, mutate)}

    def promote(self, current_agent: dict[str, Any]) -> dict[str, Any]:
        return self.claim_p1(current_agent)

    def forward_request(
        self,
        current_agent: dict[str, Any],
        controller: dict[str, Any],
        request: dict[str, Any],
    ) -> dict[str, Any]:
        current = agent_identity(current_agent)
        target = agent_identity(controller)
        if current.get("workspace_id") != self.workspace_id:
            raise RouterError("worker is outside this workspace")
        if target.get("workspace_id") != self.workspace_id:
            raise RouterError("controller is outside this workspace")

        envelope = {
            "schema_version": "herdr-p1-request/v1",
            "workspace_id": self.workspace_id,
            "from": current,
            "controller": target,
            "request": request,
        }
        request_id = deterministic_request_id(envelope)
        envelope["request_id"] = request_id

        def mutate(state: dict[str, Any]) -> bool:
            queued_ids = {item.get("request_id") for item in state.setdefault("inbox", [])}
            if request_id in queued_ids:
                return False
            state["inbox"].append(json.loads(json.dumps(envelope, sort_keys=True)))
            return True

        inserted = bool(mutate_state(self.state_path, mutate))
        if inserted and target.get("status") in SETTLED_STATUSES:
            self.client.signal_agent(P1_NAME, request_id)
        return {"action": "FORWARD", "workspace_id": self.workspace_id, "request_id": request_id}

    def inbox_requests(self) -> list[dict[str, Any]]:
        state = load_state(self.state_path)
        return [item["request"] | {"request_id": item["request_id"]} for item in state["inbox"]]


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
        "workspace_id": envelope["workspace_id"],
        "from": immutable_agent_identity(envelope["from"]),
        "request": envelope["request"],
    }


def immutable_agent_identity(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": identity.get("name"),
        "session_id": identity.get("session_id"),
    }
