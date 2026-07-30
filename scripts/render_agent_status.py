#!/usr/bin/env python3
"""Render fixed Herdr role and current task from workspace state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def render_agent_status(state: dict) -> list[str]:
    rows = []
    for slot in sorted(state["slots"]):
        value = state["slots"][slot]
        task = value.get("task_summary") or "-"
        rows.append(
            f"{slot} | {value['role_name']} | {value['status']} | {task}"
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path)
    args = parser.parse_args()
    state = json.loads(args.state.read_text(encoding="utf-8"))
    print("\n".join(render_agent_status(state)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
