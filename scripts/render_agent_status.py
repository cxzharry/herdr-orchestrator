#!/usr/bin/env python3
"""Render live Herdr P1-P9 agent status for P1 observability."""

from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any

try:
    from scripts.agent_naming import slot_from_agent_name
except ModuleNotFoundError:
    from agent_naming import slot_from_agent_name


def render_agent_status(agents: list[dict[str, Any]]) -> str:
    rows = []
    for agent in agents:
        name = agent.get("name")
        slot = slot_from_agent_name(name)
        if not slot:
            continue
        rows.append((int(slot[1:]), slot, name, agent.get("agent_status", "")))
    rows.sort(key=lambda row: (row[0], row[2]))
    return "\n".join(f"{slot} {name} {status}" for _, slot, name, status in rows)


def list_live_agents() -> list[dict[str, Any]]:
    result = subprocess.run(
        ["herdr", "agent", "list"],
        check=False,
        capture_output=True,
        text=True,
    )
    stream = result.stdout.strip() or result.stderr.strip()
    if result.returncode:
        raise RuntimeError(stream)
    return json.loads(stream)["result"]["agents"]


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(render_agent_status(list_live_agents()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
