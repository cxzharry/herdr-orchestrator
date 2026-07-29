#!/usr/bin/env python3
"""Socket-scoped runtime registry for dynamic Herdr agent names."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import tempfile
from collections.abc import Collection
from pathlib import Path
from typing import Callable

from scripts.agent_naming import format_agent_name


class RegistryError(RuntimeError):
    pass


class RuntimeRegistry:
    def __init__(self, runtime_root: Path | str, socket_key: str):
        self.path = Path(runtime_root) / socket_key / "runtime-registry.json"
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def reserve_visible_name(
        self,
        *,
        controller_scope: str,
        slot: str,
        role: str,
        reservation_token: str,
        task: str | None = None,
        live_names: Collection[str] = (),
    ) -> dict:
        def mutate(state: dict) -> dict:
            registered = state["controller_scopes"].get(controller_scope)
            if registered is not None:
                return copy.deepcopy(registered)

            pending = _pending_for_scope(state, controller_scope)
            if pending is not None:
                if pending["reservation_token"] != reservation_token:
                    raise RegistryError("pending reservation belongs to a different token")
                return copy.deepcopy(pending)

            occupied = set(live_names)
            occupied.update(state["visible_names"].keys())
            name = format_agent_name(
                slot,
                role,
                task,
                occupied=occupied,
                collision_key=controller_scope,
            )
            record = {
                "controller_scope": controller_scope,
                "session_id": None,
                "slot": slot.upper(),
                "reservation_token": reservation_token,
                "name": name,
                "status": "pending",
            }
            state["visible_names"][name] = record
            return copy.deepcopy(record)

        return self._update(mutate)

    def finalize_visible_name(
        self,
        *,
        controller_scope: str,
        reservation_token: str,
        session_id: str,
        name: str,
    ) -> dict:
        def mutate(state: dict) -> dict:
            record = state["visible_names"].get(name)
            if record is None:
                raise RegistryError("unknown visible-name reservation")
            if record["controller_scope"] != controller_scope:
                raise RegistryError("visible name belongs to a different controller scope")
            if record["reservation_token"] != reservation_token:
                raise RegistryError("reservation token does not match")
            _lease_session(
                state,
                session_id=session_id,
                controller_scope=controller_scope,
                contract_id=None,
                lane_id=None,
                generation=None,
            )
            record["session_id"] = session_id
            record["status"] = "finalized"
            state["controller_scopes"][controller_scope] = {
                "controller_scope": controller_scope,
                "session_id": session_id,
                "slot": record["slot"],
                "reservation_token": reservation_token,
                "name": name,
                "status": "finalized",
            }
            return copy.deepcopy(state["controller_scopes"][controller_scope])

        return self._update(mutate)

    def release_visible_name(
        self,
        *,
        controller_scope: str,
        session_id: str | None,
        name: str,
    ) -> dict:
        def mutate(state: dict) -> dict:
            record = state["visible_names"].get(name)
            if record is None:
                return {"released": False, "name": name}
            if record["controller_scope"] != controller_scope:
                raise RegistryError("visible name belongs to a different controller scope")
            if record.get("session_id") not in {None, session_id}:
                raise RegistryError("visible name belongs to a different session")
            del state["visible_names"][name]
            if session_id is not None:
                state["live_sessions"].pop(session_id, None)
            return {"released": True, "name": name}

        return self._update(mutate)

    def lease_session(
        self,
        *,
        session_id: str,
        controller_scope: str,
        contract_id: str,
        lane_id: str,
        generation: str,
    ) -> dict:
        def mutate(state: dict) -> dict:
            return _lease_session(
                state,
                session_id=session_id,
                controller_scope=controller_scope,
                contract_id=contract_id,
                lane_id=lane_id,
                generation=generation,
            )

        return self._update(mutate)

    def claim_legacy_resources(
        self,
        *,
        controller_scope: str,
        session_id: str,
    ) -> dict:
        def mutate(state: dict) -> dict:
            claimed = state["legacy_resources"].get("global")
            if claimed is not None:
                if (
                    claimed["controller_scope"] == controller_scope
                    and claimed["session_id"] == session_id
                ):
                    return copy.deepcopy(claimed)
                raise RegistryError("legacy resources already claimed")
            claimed = {
                "controller_scope": controller_scope,
                "session_id": session_id,
                "resources": ["p1-inbox", "worker-pool-v1"],
            }
            state["legacy_resources"]["global"] = claimed
            return copy.deepcopy(claimed)

        return self._update(mutate)

    def read(self) -> dict:
        if not self.path.exists():
            return _empty_state()
        return _upgrade(json.loads(self.path.read_text(encoding="utf-8")))

    def _update(self, mutator: Callable[[dict], dict]) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = self.read()
            before = json.dumps(state, sort_keys=True, separators=(",", ":"))
            result = mutator(state)
            after = json.dumps(state, sort_keys=True, separators=(",", ":"))
            if after != before:
                state["revision"] = int(state.get("revision", 0)) + 1
                _write_json_atomic(self.path, state)
            return result


def _pending_for_scope(state: dict, controller_scope: str) -> dict | None:
    for record in state["visible_names"].values():
        if (
            record["controller_scope"] == controller_scope
            and record["status"] == "pending"
        ):
            return record
    return None


def _lease_session(
    state: dict,
    *,
    session_id: str,
    controller_scope: str,
    contract_id: str | None,
    lane_id: str | None,
    generation: str | None,
) -> dict:
    existing = state["live_sessions"].get(session_id)
    requested = {
        "session_id": session_id,
        "controller_scope": controller_scope,
        "contract_id": contract_id,
        "lane_id": lane_id,
        "generation": generation,
    }
    if existing is not None:
        same_scope = existing["controller_scope"] == controller_scope
        compatible_lane = all(
            existing.get(key) in {None, requested[key]}
            for key in ("contract_id", "lane_id", "generation")
        )
        if same_scope and compatible_lane:
            existing.update(
                {
                    key: requested[key]
                    for key in ("contract_id", "lane_id", "generation")
                    if requested[key] is not None
                }
            )
            return copy.deepcopy(existing)
        raise RegistryError("session is already leased")
    state["live_sessions"][session_id] = requested
    return copy.deepcopy(requested)


def _empty_state() -> dict:
    return {
        "schema_version": "herdr-runtime-registry/v1",
        "revision": 0,
        "controller_scopes": {},
        "visible_names": {},
        "live_sessions": {},
        "legacy_resources": {},
    }


def _upgrade(value: dict) -> dict:
    if value.get("schema_version") != "herdr-runtime-registry/v1":
        raise RegistryError("unsupported runtime-registry schema_version")
    upgraded = copy.deepcopy(value)
    upgraded.setdefault("revision", 0)
    upgraded.setdefault("controller_scopes", {})
    upgraded.setdefault("visible_names", {})
    upgraded.setdefault("live_sessions", {})
    upgraded.setdefault("legacy_resources", {})
    return upgraded


def _write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
