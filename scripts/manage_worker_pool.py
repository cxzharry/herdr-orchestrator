#!/usr/bin/env python3
"""Prepare and bind a small reusable Herdr P2-P4 worker pool."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any


SETTLED_STATUSES = {"idle", "done"}
SLOTS = ("P2", "P3", "P4")


class PoolError(RuntimeError):
    pass


def optional_session_id(agent: dict[str, Any]) -> str | None:
    session = agent.get("agent_session") or {}
    value = session.get("value")
    return str(value) if value else None


def session_id(agent: dict[str, Any]) -> str:
    value = optional_session_id(agent)
    if value is None:
        raise PoolError(f"{agent.get('name', 'unknown')} has no live session")
    return value


class JsonState:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


class WorkerPool:
    def __init__(
        self,
        client: Any,
        state_path: Path,
        workspace_id: str,
        anchor_pane_id: str,
    ):
        self.client = client
        self.state = JsonState(state_path)
        self.workspace_id = workspace_id
        self.anchor_pane_id = anchor_pane_id

    def prepare(self, contract_id: str, cwd: str, count: int = 3) -> dict[str, Any]:
        if count < 1 or count > len(SLOTS):
            raise PoolError("worker count must be between 1 and 3")
        root = str(Path(cwd).resolve())
        current = self.state.load()
        live = {agent.get("name"): agent for agent in self.client.list_agents()}

        if current:
            self._validate_state(current, live)
            if current["contract_id"] == contract_id:
                if current["root"] != root:
                    raise PoolError("same contract cannot change root")
                return self._result("reused", current)
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
                rebound = optional_session_id(ready[worker["name"]])
                if rebound and rebound != previous_sessions[worker["name"]]:
                    worker["session_id"] = rebound
                    worker["rebind_pending"] = False
                    worker.pop("previous_session_id", None)
                else:
                    worker["input_ready"] = True
            current["contract_id"] = contract_id
            current["root"] = root
            self.state.save(current)
            return self._result("reset", current)

        slots = SLOTS[:count]
        names = [f"hdr_{slot.lower()}" for slot in slots]
        collisions = sorted(name for name in names if name in live)
        if collisions:
            raise PoolError(
                "refusing unowned live agent name(s): " + ", ".join(collisions)
            )

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
            started_session = optional_session_id(ready[request["name"]])
            workers.append(
                {
                    **request,
                    "session_id": started_session,
                    "input_ready": True,
                    "rebind_pending": started_session is None,
                }
            )

        value = {
            "schema_version": "herdr-worker-pool/v1",
            "workspace_id": self.workspace_id,
            "anchor_pane_id": self.anchor_pane_id,
            "contract_id": contract_id,
            "root": root,
            "workers": workers,
        }
        self.state.save(value)
        return self._result("created", value)

    def bind(self, contract_id: str) -> dict[str, Any]:
        current = self.state.load()
        if not current:
            raise PoolError("worker pool is not prepared")
        if current["contract_id"] != contract_id:
            raise PoolError("contract mismatch")

        live = {agent.get("name"): agent for agent in self.client.list_agents()}
        for worker in current["workers"]:
            agent = live.get(worker["name"])
            if not agent or agent.get("pane_id") != worker["pane_id"]:
                raise PoolError(f"{worker['name']} live identity mismatch")
            new_session = session_id(agent)
            if worker.get("rebind_pending"):
                previous_session = worker.get("previous_session_id")
                if previous_session and new_session == previous_session:
                    raise PoolError(f"{worker['name']} session has not changed")
                worker["session_id"] = new_session
                worker["rebind_pending"] = False
                worker.pop("previous_session_id", None)

        self.state.save(current)
        return self._result("bound", current)

    def _validate_state(
        self,
        current: dict[str, Any],
        live: dict[str, dict[str, Any]],
    ) -> None:
        if current.get("workspace_id") != self.workspace_id:
            raise PoolError("workspace mismatch")
        for worker in current.get("workers", []):
            agent = live.get(worker["name"])
            if not agent:
                raise PoolError(f"{worker['name']} is no longer live")
            if agent.get("pane_id") != worker["pane_id"]:
                raise PoolError(f"{worker['name']} pane identity mismatch")
            status = agent.get("agent_status")
            if status not in SETTLED_STATUSES:
                raise PoolError(f"{worker['name']} is {status}; refusing to hijack")
            if not worker.get("rebind_pending") and session_id(agent) != worker["session_id"]:
                raise PoolError(f"{worker['name']} session identity mismatch")

    @staticmethod
    def _validate_argv(argv: list[str]) -> None:
        rendered = " ".join(argv)
        required = ("--yolo", "--model gpt-5.5", 'model_reasoning_effort="medium"')
        missing = [value for value in required if value not in rendered]
        if missing:
            raise PoolError("worker launch invariant failed: " + ", ".join(missing))

    @staticmethod
    def _result(action: str, value: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "ready",
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
        try:
            payload = self._run(args)
        except PoolError as error:
            if "agent_pane_busy" not in str(error):
                raise
            time.sleep(0.25)
            payload = self._run(args)
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


def default_state_path(workspace_id: str) -> Path:
    return Path.home() / ".codex" / "herdr-pools" / f"{workspace_id}.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--workspace", default=os.environ.get("HERDR_WORKSPACE_ID"))
    parser.add_argument("--anchor-pane", default=os.environ.get("HERDR_PANE_ID"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--contract-id", required=True)
    prepare.add_argument("--cwd", required=True)
    prepare.add_argument("--count", type=int, default=3)

    bind = subparsers.add_parser("bind")
    bind.add_argument("--contract-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.environ.get("HERDR_ENV") != "1":
        raise SystemExit("HERDR_ENV=1 is required")
    if not args.workspace or not args.anchor_pane:
        raise SystemExit("Herdr workspace and anchor pane are required")
    state_path = args.state_file or default_state_path(args.workspace)
    pool = WorkerPool(
        client=HerdrClient(args.anchor_pane),
        state_path=state_path,
        workspace_id=args.workspace,
        anchor_pane_id=args.anchor_pane,
    )
    try:
        if args.command == "prepare":
            result = pool.prepare(args.contract_id, args.cwd, args.count)
        else:
            result = pool.bind(args.contract_id)
    except PoolError as error:
        print(json.dumps({"status": "error", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
