#!/usr/bin/env python3
"""Prepare and bind a small reusable Herdr P2-P4 worker pool."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

try:
    from scripts.agent_naming import format_agent_name
except ModuleNotFoundError:
    from agent_naming import format_agent_name


SETTLED_STATUSES = {"idle", "done"}
SLOTS = ("P2", "P3", "P4")
START_WORKER_BUSY_TIMEOUT = 2.0
START_WORKER_BUSY_BACKOFF = 0.05


class PoolError(RuntimeError):
    pass


def optional_session_id(agent: dict[str, Any]) -> str | None:
    session = agent.get("agent_session") or {}
    value = session.get("value")
    return str(value) if value else None


def validate_controller_scope(value: str) -> str:
    scope = str(value)
    if not re.fullmatch(r"[a-f0-9]{4,32}", scope):
        raise PoolError("controller scope must be lowercase hex")
    return scope


def ready_name(slot: str, controller_scope: str, occupied: set[str]) -> str:
    return format_agent_name(
        slot,
        "worker",
        "ready",
        occupied=occupied,
        collision_key=f"{controller_scope}:{slot}",
    )


def live_agent_for_worker(
    worker: dict[str, Any],
    agents: list[dict[str, Any]],
) -> dict[str, Any] | None:
    expected_session = worker.get("session_id")
    if expected_session:
        matches = [
            agent
            for agent in agents
            if optional_session_id(agent) == expected_session
        ]
        if len(matches) > 1:
            raise PoolError(f"{worker['slot']} session is not unique")
        if matches:
            return matches[0]
    matches = [
        agent
        for agent in agents
        if agent.get("name") == worker.get("name")
    ]
    if len(matches) > 1:
        raise PoolError(f"{worker['slot']} has multiple live agents")
    return matches[0] if matches else None


def verified_agent_by_session(
    agents: list[dict[str, Any]],
    session_id: str | None,
    expected_name: str,
) -> dict[str, Any]:
    matches = [
        agent
        for agent in agents
        if optional_session_id(agent) == session_id
        and agent.get("name") == expected_name
    ]
    if len(matches) != 1:
        raise PoolError("worker rename was not verified")
    return matches[0]


class JsonState:
    def __init__(self, path: Path):
        self.path = path
        self._fingerprint: str | None = None

    @contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def load(self) -> dict[str, Any] | None:
        if (
            not self.path.is_file()
            and (
                self.path.name == "active.json"
                or self.path.name.startswith("active-")
            )
        ):
            legacy = sorted(self.path.parent.glob("w*.json"))
            if len(legacy) > 1:
                raise PoolError(
                    "multiple legacy worker pools found; pass --state-file explicitly"
                )
            if legacy:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                legacy[0].replace(self.path)
        if not self.path.is_file():
            self._fingerprint = None
            return None
        payload = self.path.read_bytes()
        self._fingerprint = hashlib.sha256(payload).hexdigest()
        return json.loads(payload)

    def save(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        current_fingerprint = None
        if self.path.is_file():
            current_fingerprint = hashlib.sha256(self.path.read_bytes()).hexdigest()
        if current_fingerprint != self._fingerprint:
            raise PoolError("worker pool state changed concurrently")
        encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        temporary.write_bytes(encoded)
        temporary.replace(self.path)
        self._fingerprint = hashlib.sha256(encoded).hexdigest()


class WorkerPool:
    def __init__(
        self,
        client: Any,
        state_path: Path,
        workspace_id: str,
        anchor_pane_id: str,
        controller_scope: str,
    ):
        self.client = client
        self.state = JsonState(state_path)
        self.workspace_id = workspace_id
        self.anchor_pane_id = anchor_pane_id
        self.controller_scope = validate_controller_scope(controller_scope)
        self.herdr_session_key = current_herdr_session_key()

    def prepare(self, contract_id: str, cwd: str, count: int = 3) -> dict[str, Any]:
        with self.state.locked():
            return self._prepare(contract_id, cwd, count)

    def _prepare(self, contract_id: str, cwd: str, count: int) -> dict[str, Any]:
        if count < 1 or count > len(SLOTS):
            raise PoolError("worker count must be between 1 and 3")
        root = str(Path(cwd).resolve())
        current = self.state.load()
        live = self.client.list_agents()

        if current:
            state_changed = self._validate_state_scope(current)
            if current["contract_id"] == contract_id and current["root"] != root:
                raise PoolError("same contract cannot change root")
            same_contract = current["contract_id"] == contract_id
            rebound, missing, busy = self._reconcile_state(
                current,
                live,
                allow_busy=same_contract,
            )
            current_slots = {worker["slot"] for worker in current["workers"]}
            occupied = {agent.get("name") for agent in live if agent.get("name")}
            for slot in SLOTS[:count]:
                if slot in current_slots:
                    continue
                name = ready_name(slot, self.controller_scope, occupied)
                if name in occupied:
                    raise PoolError(f"refusing unowned live agent name: {name}")
                missing.append({"slot": slot, "name": name})
                occupied.add(name)
            if missing:
                self._recover_missing(current, missing, root)
            if same_contract:
                if missing:
                    action = "recovered"
                elif rebound:
                    action = "rebound"
                elif busy:
                    action = "attached"
                else:
                    action = "reused"
                if state_changed or missing or rebound:
                    self.state.save(current)
                return self._result(
                    action,
                    current,
                    status="busy" if busy else "ready",
                )
            previous_sessions = {}
            for worker in current["workers"]:
                previous_sessions[worker["name"]] = worker["session_id"]
                self.client.reset(worker["name"])
                worker["previous_session_id"] = worker["session_id"]
                worker["rebind_pending"] = True
            ready = {
                agent["name"]: agent
                for agent in self.client.ensure_ready(
                    current["workers"],
                    previous_sessions,
                )
            }
            for worker in current["workers"]:
                self._validate_agent_workspace(
                    worker["name"],
                    ready[worker["name"]],
                )
                rebound = optional_session_id(ready[worker["name"]])
                if rebound and rebound != previous_sessions[worker["name"]]:
                    worker["session_id"] = rebound
                    worker["rebind_pending"] = False
                    worker.pop("previous_session_id", None)
                else:
                    worker["input_ready"] = True
                occupied = {
                    agent.get("name")
                    for agent in self.client.list_agents()
                    if agent.get("name") and optional_session_id(agent) != worker.get("session_id")
                }
                expected = ready_name(worker["slot"], self.controller_scope, occupied)
                if worker["name"] != expected:
                    self.client.rename_agent(worker["name"], expected)
                    worker["name"] = expected
            current["contract_id"] = contract_id
            current["root"] = root
            self.state.save(current)
            return self._result("reset", current)

        slots = SLOTS[:count]
        occupied = {agent.get("name") for agent in live if agent.get("name")}
        names = []
        for slot in slots:
            name = ready_name(slot, self.controller_scope, occupied)
            names.append(name)
            occupied.add(name)

        panes = self.client.create_panes(count, root)
        requested = [
            {"slot": slot, "name": name, "pane_id": pane}
            for slot, name, pane in zip(slots, names, panes)
        ]
        started = self.client.start_workers(requested)
        ready = {
            agent["name"]: agent
            for agent in self.client.ensure_ready(requested)
        }
        workers = []
        for request, response in zip(requested, started):
            self._validate_argv(response.get("argv") or [])
            self._validate_agent_workspace(
                request["name"],
                ready[request["name"]],
            )
            started_session = optional_session_id(ready[request["name"]])
            workers.append(
                {
                    **request,
                    "session_id": started_session,
                    "workspace_id": ready[request["name"]].get("workspace_id"),
                    "terminal_id": ready[request["name"]].get("terminal_id"),
                    "input_ready": True,
                    "rebind_pending": started_session is None,
                }
            )

        value = {
            "schema_version": "herdr-worker-pool/v2",
            "herdr_session_key": self.herdr_session_key,
            "controller_scope": self.controller_scope,
            "workspace_id": self.workspace_id,
            "anchor_pane_id": self.anchor_pane_id,
            "contract_id": contract_id,
            "root": root,
            "workers": workers,
        }
        self.state.save(value)
        return self._result("created", value)

    def bind(
        self,
        contract_id: str,
        wait_seconds: float = 0,
    ) -> dict[str, Any]:
        with self.state.locked():
            return self._bind(contract_id, wait_seconds)

    def _bind(self, contract_id: str, wait_seconds: float) -> dict[str, Any]:
        if wait_seconds < 0:
            raise PoolError("bind wait must not be negative")
        current = self.state.load()
        if not current:
            raise PoolError("worker pool is not prepared")
        self._validate_state_scope(current)
        if current["contract_id"] != contract_id:
            raise PoolError("contract mismatch")

        deadline = time.monotonic() + wait_seconds
        while True:
            live = self.client.list_agents()
            pending = []
            for worker in current["workers"]:
                agent = live_agent_for_worker(worker, live)
                if not agent:
                    raise PoolError(f"{worker['name']} is no longer live")
                self._validate_agent_workspace(worker["name"], agent)
                if agent.get("name") != worker.get("name"):
                    worker["name"] = agent.get("name")
                new_session = optional_session_id(agent)
                self._validate_pending_terminal(worker, agent)
                if agent.get("pane_id") != worker["pane_id"]:
                    if (
                        not worker.get("rebind_pending")
                        and new_session != worker.get("session_id")
                    ):
                        raise PoolError(
                            f"{worker['name']} live identity mismatch"
                        )
                    worker["pane_id"] = agent["pane_id"]
                    worker["workspace_id"] = agent.get("workspace_id")
                if worker.get("rebind_pending"):
                    previous_session = worker.get("previous_session_id")
                    if not new_session or (
                        previous_session and new_session == previous_session
                    ):
                        pending.append(worker["name"])
                        continue
                    worker["session_id"] = new_session
                    worker["rebind_pending"] = False
                    worker.pop("previous_session_id", None)
                elif new_session != worker["session_id"]:
                    raise PoolError(
                        f"{worker['name']} session identity mismatch"
                    )
            if not pending or time.monotonic() >= deadline:
                break
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))

        self.state.save(current)
        return self._result("pending" if pending else "bound", current)

    def _reconcile_state(
        self,
        current: dict[str, Any],
        live: list[dict[str, Any]],
        allow_busy: bool,
    ) -> tuple[bool, list[dict[str, Any]], bool]:
        rebound = False
        missing = []
        busy = False
        for worker in current.get("workers", []):
            agent = live_agent_for_worker(worker, live)
            if not agent:
                missing.append(worker)
                continue
            self._validate_agent_workspace(worker["name"], agent)
            if agent.get("name") != worker.get("name"):
                worker["name"] = agent.get("name")
                rebound = True
            if worker.get("recovery_pending"):
                if agent.get("pane_id") != worker.get("pane_id"):
                    raise PoolError(
                        f"{worker['name']} recovery pane identity mismatch"
                    )
                worker["session_id"] = optional_session_id(agent)
                worker["workspace_id"] = agent.get("workspace_id")
                worker["terminal_id"] = agent.get("terminal_id")
                worker["input_ready"] = bool(agent.get("interactive_ready"))
                worker["rebind_pending"] = worker["session_id"] is None
                worker.pop("recovery_pending", None)
                rebound = True
            live_session = optional_session_id(agent)
            self._validate_pending_terminal(worker, agent)
            if agent.get("pane_id") != worker["pane_id"]:
                if (
                    not worker.get("rebind_pending")
                    and live_session != worker.get("session_id")
                ):
                    raise PoolError(f"{worker['name']} pane identity mismatch")
                worker["pane_id"] = agent["pane_id"]
                worker["workspace_id"] = agent.get("workspace_id")
                rebound = True
            status = agent.get("agent_status")
            if agent.get("name", "").startswith("hdr_p"):
                occupied = {
                    item.get("name")
                    for item in self.client.list_agents()
                    if item.get("name")
                    and optional_session_id(item) != worker.get("session_id")
                }
                expected = ready_name(worker["slot"], self.controller_scope, occupied)
                self.client.rename_agent(agent["pane_id"], expected)
                agent = verified_agent_by_session(
                    self.client.list_agents(),
                    worker["session_id"],
                    expected,
                )
                worker["name"] = agent["name"]
                rebound = True
            if status not in SETTLED_STATUSES:
                if not allow_busy:
                    raise PoolError(
                        f"{worker['name']} is {status}; refusing to hijack"
                    )
                busy = True
            if worker.get("rebind_pending"):
                previous_session = worker.get("previous_session_id")
                if live_session and (
                    not previous_session or live_session != previous_session
                ):
                    worker["session_id"] = live_session
                    worker["rebind_pending"] = False
                    worker.pop("previous_session_id", None)
                    rebound = True
            elif live_session != worker["session_id"]:
                raise PoolError(f"{worker['name']} session identity mismatch")
            if not worker.get("terminal_id") and agent.get("terminal_id"):
                worker["terminal_id"] = agent["terminal_id"]
                rebound = True
        return rebound, missing, busy

    def _recover_missing(
        self,
        current: dict[str, Any],
        missing: list[dict[str, Any]],
        root: str,
    ) -> None:
        panes = self.client.create_panes(len(missing), root)
        requested = [
            {
                "slot": worker["slot"],
                "name": worker["name"],
                "pane_id": pane,
            }
            for worker, pane in zip(missing, panes)
        ]
        reservations = {
            request["name"]: {
                **request,
                "session_id": None,
                "workspace_id": self.workspace_id,
                "terminal_id": None,
                "input_ready": False,
                "rebind_pending": True,
                "recovery_pending": True,
            }
            for request in requested
        }
        self._replace_workers(current, reservations)
        self.state.save(current)

        try:
            started = self.client.start_workers(requested)
            for response in started:
                self._validate_argv(response.get("argv") or [])
            ready = {
                agent["name"]: agent
                for agent in self.client.ensure_ready(requested)
            }
            replacements = {}
            for request in requested:
                agent = ready[request["name"]]
                self._validate_agent_workspace(request["name"], agent)
                started_session = optional_session_id(agent)
                replacements[request["name"]] = {
                    **request,
                    "session_id": started_session,
                    "workspace_id": agent.get("workspace_id"),
                    "terminal_id": agent.get("terminal_id"),
                    "input_ready": True,
                    "rebind_pending": started_session is None,
                }
            self._replace_workers(current, replacements)
            self.state.save(current)
        except Exception:
            for request in requested:
                try:
                    self.client.quarantine(request["name"])
                except (PoolError, StopIteration):
                    pass
            retry = {
                request["name"]: {
                    **reservations[request["name"]],
                    "pane_id": None,
                }
                for request in requested
            }
            self._replace_workers(current, retry)
            self.state.save(current)
            raise

    @staticmethod
    def _replace_workers(
        current: dict[str, Any],
        replacements: dict[str, dict[str, Any]],
    ) -> None:
        workers_by_slot = {
            worker["slot"]: worker for worker in current["workers"]
        }
        for worker in replacements.values():
            workers_by_slot[worker["slot"]] = worker
        current["workers"] = [
            workers_by_slot[slot]
            for slot in SLOTS
            if slot in workers_by_slot
        ]

    def _validate_state_scope(self, current: dict[str, Any]) -> bool:
        schema = current.get("schema_version")
        if schema not in {"herdr-worker-pool/v1", "herdr-worker-pool/v2"}:
            raise PoolError("unsupported worker pool schema_version")
        stored_scope = current.get("controller_scope")
        if stored_scope and stored_scope != self.controller_scope:
            raise PoolError("controller scope mismatch")
        stored_workspace = current.get("workspace_id")
        if stored_workspace and stored_workspace != self.workspace_id:
            raise PoolError("workspace mismatch")
        changed = False
        if not stored_scope:
            current["controller_scope"] = self.controller_scope
            changed = True
        if schema != "herdr-worker-pool/v2":
            current["schema_version"] = "herdr-worker-pool/v2"
            changed = True
        stored = current.get("herdr_session_key")
        if stored == "unspecified":
            current["herdr_session_key"] = self.herdr_session_key
            return True
        if stored and stored != self.herdr_session_key:
            raise PoolError("Herdr session mismatch")
        if stored:
            return changed
        current["herdr_session_key"] = self.herdr_session_key
        return True

    def _validate_agent_workspace(
        self,
        worker_name: str,
        agent: dict[str, Any],
    ) -> None:
        workspace = agent.get("workspace_id")
        if workspace and workspace != self.workspace_id:
            raise PoolError(f"{worker_name} workspace mismatch")

    @staticmethod
    def _validate_pending_terminal(
        worker: dict[str, Any],
        agent: dict[str, Any],
    ) -> None:
        if worker.get("recovery_pending"):
            raise PoolError(
                f"{worker['name']} recovery is incomplete; run prepare"
            )
        if not worker.get("rebind_pending"):
            return
        expected = worker.get("terminal_id")
        if not expected:
            raise PoolError(
                f"{worker['name']} pending terminal identity is unavailable"
            )
        if agent.get("terminal_id") != expected:
            raise PoolError(f"{worker['name']} terminal identity mismatch")

    @staticmethod
    def _validate_argv(argv: list[str]) -> None:
        rendered = " ".join(argv)
        required = ("--yolo", "--model gpt-5.5", 'model_reasoning_effort="medium"')
        missing = [value for value in required if value not in rendered]
        if missing:
            raise PoolError("worker launch invariant failed: " + ", ".join(missing))

    @staticmethod
    def _result(
        action: str,
        value: dict[str, Any],
        status: str = "ready",
    ) -> dict[str, Any]:
        return {
            "status": status,
            "action": action,
            "contract_id": value["contract_id"],
            "root": value["root"],
            "workers": value["workers"],
        }


class HerdrClient:
    def __init__(self, anchor_pane_id: str):
        self.anchor_pane_id = anchor_pane_id

    def _run(self, args: list[str]) -> dict[str, Any]:
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

    def list_agents(self) -> list[dict[str, Any]]:
        return self._run(["agent", "list"])["result"]["agents"]

    def create_panes(self, count: int, cwd: str) -> list[str]:
        panes = []
        anchor = self.anchor_pane_id
        for index in range(count):
            direction = "right" if index == 0 else "down"
            payload = self._run(
                [
                    "pane",
                    "split",
                    "--pane",
                    anchor,
                    "--direction",
                    direction,
                    "--cwd",
                    cwd,
                    "--no-focus",
                ]
            )
            pane = payload["result"]["pane"]["pane_id"]
            panes.append(pane)
            anchor = pane
        return panes

    def start_workers(self, workers: list[dict[str, str]]) -> list[dict[str, Any]]:
        with ThreadPoolExecutor(max_workers=len(workers)) as executor:
            return list(executor.map(self._start_worker, workers))

    def _start_worker(self, worker: dict[str, str]) -> dict[str, Any]:
        args = [
            "agent",
            "start",
            worker["name"],
            "--kind",
            "codex",
            "--pane",
            worker["pane_id"],
            "--",
            "--yolo",
            "--model",
            "gpt-5.5",
            "-c",
            'model_reasoning_effort="medium"',
            "-c",
            "mcp_servers.pencil.enabled=false",
            "-c",
            "mcp_servers.notion.enabled=false",
            "-c",
            "mcp_servers.figma.enabled=false",
            "-c",
            "mcp_servers.atlassian.enabled=false",
            "-c",
            "mcp_servers.openaiDeveloperDocs.enabled=false",
        ]
        deadline = time.monotonic() + START_WORKER_BUSY_TIMEOUT
        while True:
            try:
                payload = self._run(args)
                break
            except PoolError as error:
                if "agent_pane_busy" not in str(error):
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise
                time.sleep(min(START_WORKER_BUSY_BACKOFF, remaining))
        return payload["result"]

    def ensure_ready(
        self,
        workers: list[dict[str, str]],
        previous_sessions: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        previous_sessions = previous_sessions or {}
        pending = {worker["name"]: worker for worker in workers}
        ready: dict[str, dict[str, Any]] = {}
        last_enter: dict[str, float] = {}
        deadline = time.monotonic() + 15

        while pending and time.monotonic() < deadline:
            live = {agent.get("name"): agent for agent in self.list_agents()}
            for name, worker in list(pending.items()):
                agent = live.get(name)
                current_session = optional_session_id(agent or {})
                previous_session = previous_sessions.get(name)
                if (
                    agent
                    and agent.get("pane_id") == worker["pane_id"]
                    and agent.get("agent_status") in SETTLED_STATUSES
                    and (
                        (
                            current_session
                            and current_session != previous_session
                        )
                        or (
                            current_session is None
                            and not previous_session
                            and self._at_input_prompt(worker["pane_id"])
                        )
                        or (
                            current_session == previous_session
                            and previous_session is not None
                            and self._at_input_prompt(worker["pane_id"])
                        )
                    )
                ):
                    ready[name] = agent
                    pending.pop(name)
                    continue
                if (
                    current_session is None
                    and time.monotonic() - last_enter.get(name, 0) >= 1
                    and self._at_startup_gate(worker["pane_id"])
                ):
                    self._send_enter(worker["pane_id"])
                    last_enter[name] = time.monotonic()
            if pending:
                time.sleep(0.2)

        if pending:
            raise PoolError(
                "workers did not reach an input-ready session: "
                + ", ".join(sorted(pending))
            )
        return [ready[worker["name"]] for worker in workers]

    @staticmethod
    def _pane_text(pane_id: str) -> str:
        result = subprocess.run(
            [
                "herdr",
                "pane",
                "read",
                pane_id,
                "--source",
                "visible",
                "--lines",
                "40",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            return ""
        return result.stdout

    def _at_startup_gate(self, pane_id: str) -> bool:
        return "Press enter to continue" in self._pane_text(pane_id)

    def _at_input_prompt(self, pane_id: str) -> bool:
        text = self._pane_text(pane_id)
        return "›" in text and "Press enter to continue" not in text

    @staticmethod
    def _send_enter(pane_id: str) -> None:
        result = subprocess.run(
            ["herdr", "pane", "send-keys", pane_id, "enter"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise PoolError(
                f"failed to clear startup gate for {pane_id}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

    def reset(self, name: str) -> None:
        self._run(["agent", "prompt", name, "/new"])

    def quarantine(self, name: str) -> None:
        suffix = f"{time.monotonic_ns():x}"[-8:]
        orphan = f"orphan_{name.removeprefix('hdr_')}_{suffix}"
        self._run(["agent", "rename", name, orphan])

    def rename_agent(self, target: str, name: str) -> None:
        self._run(["agent", "rename", target, name])


def current_herdr_session_key() -> str:
    socket_path = os.environ.get("HERDR_SOCKET_PATH", "unspecified")
    return hashlib.sha256(socket_path.encode()).hexdigest()[:12]


def default_state_path(
    workspace_id: str,
    controller_scope: str,
    *,
    root: Path | None = None,
) -> Path:
    scope = validate_controller_scope(controller_scope)
    workspace = str(workspace_id).replace("/", "_")
    return (
        (root or Path.home() / ".codex" / "herdr-pools")
        / f"active-{current_herdr_session_key()}-{workspace}-{scope}.json"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--workspace", default=os.environ.get("HERDR_WORKSPACE_ID"))
    parser.add_argument("--anchor-pane", default=os.environ.get("HERDR_PANE_ID"))
    parser.add_argument("--controller-scope", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--contract-id", required=True)
    prepare.add_argument("--cwd", required=True)
    prepare.add_argument("--count", type=int, default=3)

    bind = subparsers.add_parser("bind")
    bind.add_argument("--contract-id", required=True)
    bind.add_argument("--wait-seconds", type=float, default=5.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.environ.get("HERDR_ENV") != "1":
        raise SystemExit("HERDR_ENV=1 is required")
    if not args.workspace or not args.anchor_pane:
        raise SystemExit("Herdr workspace and anchor pane are required")
    state_path = args.state_file or default_state_path(
        args.workspace,
        args.controller_scope,
    )
    pool = WorkerPool(
        client=HerdrClient(args.anchor_pane),
        state_path=state_path,
        workspace_id=args.workspace,
        anchor_pane_id=args.anchor_pane,
        controller_scope=args.controller_scope,
    )
    try:
        if args.command == "prepare":
            result = pool.prepare(args.contract_id, args.cwd, args.count)
        else:
            result = pool.bind(args.contract_id, args.wait_seconds)
    except PoolError as error:
        print(json.dumps({"status": "error", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
