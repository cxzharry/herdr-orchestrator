#!/usr/bin/env python3
"""Wait on receipts while tracking the live Herdr session for each lane."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.scheduler_state import atomic_update, read_state
    from scripts.validate_lane_receipt import validate_receipt
except ModuleNotFoundError:
    from scheduler_state import atomic_update, read_state
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


def _workspace_from_pane(pane_id: Any) -> str | None:
    if not pane_id:
        return None
    value = str(pane_id)
    return value.split(":", 1)[0] if ":" in value else None


def _lane_workspace(state: dict[str, Any], lane: dict[str, Any]) -> str | None:
    controller = state.get("controller") or state.get("p1") or {}
    return (
        lane.get("workspace_id")
        or lane.get("controller_workspace_id")
        or _workspace_from_pane(lane.get("pane_id"))
        or controller.get("workspace_id")
        or _workspace_from_pane(controller.get("pane_id"))
        or _workspace_from_pane(state.get("controller_scope"))
    )


def _agent_workspaces(agent: dict[str, Any]) -> set[str]:
    values = {
        str(value)
        for value in (
            agent.get("workspace_id"),
            _workspace_from_pane(agent.get("pane_id")),
        )
        if value
    }
    return values


def _workspace_mismatch_payload(
    state: dict[str, Any],
    lane: dict[str, Any],
    agent: dict[str, Any],
    session: str,
) -> dict[str, Any] | None:
    expected = _lane_workspace(state, lane)
    observed = _agent_workspaces(agent)
    if not expected or not observed or observed == {expected}:
        return None
    observed_mismatch = sorted(value for value in observed if value != expected)
    return {
        "reason": "workspace_mismatch",
        "generation": lane["generation"],
        "agent_name": lane["agent_name"],
        "pane_id": lane["pane_id"],
        "session_id": session,
        "expected_workspace_id": expected,
        "observed_workspace_id": observed_mismatch[0] if observed_mismatch else sorted(observed)[0],
        "observed_pane_id": agent.get("pane_id"),
        "observed_agent_name": agent.get("name"),
    }


def _missing_payload(lane: dict[str, Any], session: str) -> dict[str, Any]:
    return {
        "reason": "session_not_live",
        "generation": lane["generation"],
        "agent_name": lane["agent_name"],
        "pane_id": lane["pane_id"],
        "session_id": session,
    }


def reconcile_once(
    state_path: Path,
    lane_ids: list[str],
    live_agents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return current receipt and liveness observations without waiting."""
    state = read_state(state_path)
    by_session = {}
    for agent in live_agents or []:
        session = _session_id(agent)
        if session:
            by_session[session] = agent

    result: dict[str, Any] = {
        "terminal": {},
        "moved": {},
        "name_drift": {},
        "missing": {},
    }
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
            result["missing"][lane_id] = _missing_payload(lane, session)
            continue
        mismatch = _workspace_mismatch_payload(state, lane, agent, session)
        if mismatch:
            result["missing"][lane_id] = mismatch
            continue
        pane_id = agent.get("pane_id")
        if pane_id and pane_id != lane.get("pane_id"):
            result["moved"][lane_id] = {
                "previous_pane_id": lane.get("pane_id"),
                "pane_id": pane_id,
                "session_id": session,
            }
        expected_name = lane.get("expected_agent_name") or lane.get("agent_name")
        live_name = agent.get("name")
        if expected_name and live_name != expected_name:
            result["name_drift"][lane_id] = {
                "expected_agent_name": expected_name,
                "agent_name": live_name,
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
    pane_id = agent.get("pane_id")
    if not pane_id:
        raise ReceiptWaitError(f"{lane_id} live agent has no pane_id")

    def mutate(value: dict[str, Any]) -> dict[str, str] | None:
        lane = value.get("lanes", {}).get(lane_id)
        if lane is None or lane.get("session_id") != expected_session_id:
            return None
        mismatch = _workspace_mismatch_payload(
            value,
            lane,
            agent,
            expected_session_id,
        )
        if mismatch:
            raise ReceiptWaitError(f"{lane_id} workspace mismatch")
        previous_pane_id = lane.get("pane_id")
        changed = previous_pane_id != pane_id
        lane["pane_id"] = pane_id
        if agent.get("name"):
            lane["agent_name"] = agent["name"]
        if not changed:
            return None
        return {
            "previous_pane_id": str(previous_pane_id),
            "pane_id": str(pane_id),
        }

    return atomic_update(state_path, mutate)


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
        state = read_state(state_path)
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
                    mismatch = _workspace_mismatch_payload(
                        state,
                        lane,
                        agent,
                        session,
                    )
                    if mismatch:
                        missing_counts[lane_id] += 1
                        if missing_counts[lane_id] >= missing_checks:
                            lost[lane_id] = mismatch
                        continue
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
                    lost[lane_id] = _missing_payload(lane, session)
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
