#!/usr/bin/env python3
"""Wait on receipts while tracking the live Herdr session for each lane."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.validate_lane_receipt import validate_receipt
except ModuleNotFoundError:
    from validate_lane_receipt import validate_receipt


class ReceiptWaitError(RuntimeError):
    pass


class LaneLostError(ReceiptWaitError):
    def __init__(self, lost: dict[str, dict[str, Any]]):
        self.lost = lost
        super().__init__("lane session lost: " + ", ".join(sorted(lost)))


def list_live_agents() -> list[dict[str, Any]]:
    result = subprocess.run(
        ["herdr", "agent", "list"],
        check=False,
        capture_output=True,
        text=True,
    )
    stream = result.stdout.strip() or result.stderr.strip()
    if result.returncode:
        raise ReceiptWaitError(f"cannot inspect Herdr agents: {stream}")
    try:
        return json.loads(stream)["result"]["agents"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ReceiptWaitError(
            f"Herdr returned invalid agent state: {stream}"
        ) from error


def _session_id(agent: dict[str, Any]) -> str | None:
    value = (agent.get("agent_session") or {}).get("value")
    return str(value) if value else None


def reconcile_once(
    state_path: Path,
    lane_ids: list[str],
    live_agents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return current receipt and liveness observations without waiting."""
    state = json.loads(state_path.read_text(encoding="utf-8"))
    by_session = {}
    for agent in live_agents or []:
        session = _session_id(agent)
        if session:
            by_session[session] = agent

    result: dict[str, Any] = {"terminal": {}, "moved": {}, "missing": {}}
    for lane_id in lane_ids:
        lane = state.get("lanes", {}).get(lane_id)
        if lane is None:
            raise ReceiptWaitError(f"unknown lane: {lane_id}")
        receipt_path = Path(lane["receipt_path"])
        if receipt_path.is_file():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            failures = validate_receipt(receipt, state)
            if failures:
                raise ReceiptWaitError(
                    f"{lane_id} receipt invalid: " + "; ".join(failures)
                )
            result["terminal"][lane_id] = receipt["status"]
            continue
        if live_agents is None:
            continue
        session = lane.get("session_id")
        if not session:
            raise ReceiptWaitError(f"{lane_id} has no live session identity")
        agent = by_session.get(session)
        if agent is None:
            result["missing"][lane_id] = {
                "reason": "session_not_live",
                "generation": lane["generation"],
                "agent_name": lane["agent_name"],
                "pane_id": lane["pane_id"],
                "session_id": session,
            }
            continue
        pane_id = agent.get("pane_id")
        if pane_id and pane_id != lane.get("pane_id"):
            result["moved"][lane_id] = {
                "previous_pane_id": lane.get("pane_id"),
                "pane_id": pane_id,
                "session_id": session,
            }
    return result


def _rebind_lane(
    state_path: Path,
    lane_id: str,
    expected_session_id: str,
    agent: dict[str, Any],
) -> dict[str, str] | None:
    value = json.loads(state_path.read_text(encoding="utf-8"))
    lane = value.get("lanes", {}).get(lane_id)
    if lane is None or lane.get("session_id") != expected_session_id:
        return None
    pane_id = agent.get("pane_id")
    if not pane_id:
        raise ReceiptWaitError(f"{lane_id} live agent has no pane_id")

    previous_pane_id = lane.get("pane_id")
    changed = previous_pane_id != pane_id
    lane["pane_id"] = pane_id
    if agent.get("name"):
        lane["agent_name"] = agent["name"]
    if not changed:
        return None

    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{state_path.name}.",
        dir=state_path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
        os.replace(temporary, state_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {
        "previous_pane_id": str(previous_pane_id),
        "pane_id": str(pane_id),
    }


def await_lanes(
    state_path: Path,
    lane_ids: list[str],
    timeout: float,
    poll: float = 0.1,
    live_agents: Callable[[], list[dict[str, Any]]] | None = None,
    liveness_poll: float = 1.0,
    missing_checks: int = 3,
) -> dict:
    if missing_checks < 1:
        raise ReceiptWaitError("missing_checks must be at least 1")
    deadline = time.monotonic() + timeout
    next_liveness = 0.0
    missing_counts = {lane_id: 0 for lane_id in lane_ids}
    observed_identity: dict[str, tuple[int, str]] = {}
    rebound: dict[str, dict[str, str]] = {}
    while time.monotonic() < deadline:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        terminal = {}
        for lane_id in lane_ids:
            lane = state.get("lanes", {}).get(lane_id)
            if lane is None:
                raise ReceiptWaitError(f"unknown lane: {lane_id}")
            receipt_path = Path(lane["receipt_path"])
            if not receipt_path.is_file():
                continue
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            failures = validate_receipt(receipt, state)
            if failures:
                raise ReceiptWaitError(
                    f"{lane_id} receipt invalid: " + "; ".join(failures)
                )
            terminal[lane_id] = receipt["status"]
        if len(terminal) == len(lane_ids):
            result = {"status": "terminal", "lanes": terminal}
            if rebound:
                result["rebound"] = rebound
            return result

        now = time.monotonic()
        if live_agents is not None and now >= next_liveness:
            agents = live_agents()
            by_session = {
                session: agent
                for agent in agents
                if (session := _session_id(agent)) is not None
            }
            lost = {}
            for lane_id in set(lane_ids) - set(terminal):
                lane = state["lanes"][lane_id]
                session = lane.get("session_id")
                if not session:
                    raise ReceiptWaitError(
                        f"{lane_id} has no live session identity"
                    )
                identity = (lane["generation"], session)
                if observed_identity.get(lane_id) != identity:
                    observed_identity[lane_id] = identity
                    missing_counts[lane_id] = 0
                agent = by_session.get(session)
                if agent is not None:
                    missing_counts[lane_id] = 0
                    event = _rebind_lane(
                        state_path,
                        lane_id,
                        session,
                        agent,
                    )
                    if event:
                        rebound[lane_id] = event
                    continue
                missing_counts[lane_id] += 1
                if missing_counts[lane_id] >= missing_checks:
                    lost[lane_id] = {
                        "reason": "session_not_live",
                        "generation": lane["generation"],
                        "agent_name": lane["agent_name"],
                        "pane_id": lane["pane_id"],
                        "session_id": session,
                    }
            if lost:
                raise LaneLostError(lost)
            next_liveness = now + liveness_poll
        time.sleep(poll)
    missing = sorted(set(lane_ids) - set(terminal))
    raise ReceiptWaitError("timed out waiting for: " + ", ".join(missing))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-state", type=Path, required=True)
    parser.add_argument("--lane", action="append", dest="lanes", required=True)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--poll", type=float, default=0.1)
    parser.add_argument("--liveness-poll", type=float, default=1.0)
    parser.add_argument("--missing-checks", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = await_lanes(
            args.control_state,
            args.lanes,
            args.timeout,
            args.poll,
            live_agents=list_live_agents,
            liveness_poll=args.liveness_poll,
            missing_checks=args.missing_checks,
        )
    except LaneLostError as error:
        print(
            json.dumps(
                {"status": "lost", "lanes": error.lost},
                indent=2,
            )
        )
        return 2
    except (OSError, ValueError, ReceiptWaitError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
