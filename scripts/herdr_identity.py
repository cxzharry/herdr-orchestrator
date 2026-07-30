#!/usr/bin/env python3
"""Herdr live-agent identity helpers and fixed role names."""

from __future__ import annotations


ROLE_NAMES = {
    "P1": "p1_orchestrator",
    "P2": "p2_impl",
    "P3": "p3_impl",
    "P4": "p4_impl",
    "P5": "p5_integration",
    "P6": "p6_review",
    "P7": "p7_qc",
    "P8": "p8_design",
    "P9": "p9_persona",
}


def agent_identity(agent: dict) -> dict:
    nested = agent.get("agent_session") or {}
    session = nested.get("value")
    return {
        "name": agent.get("name") or "",
        "pane_id": agent.get("pane_id"),
        "workspace_id": agent.get("workspace_id"),
        "terminal_id": agent.get("terminal_id"),
        "session_id": str(session) if session else None,
        "status": agent.get("agent_status"),
    }


def fixed_role_name(slot: str, workspace_id: str, occupied: set[str]) -> str:
    base = ROLE_NAMES[slot]
    return base if base not in occupied else f"{base}_{workspace_id}"
