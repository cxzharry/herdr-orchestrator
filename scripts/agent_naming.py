#!/usr/bin/env python3
"""Pure visible-name helpers for Herdr P1-P9 agents."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Collection


MAX_AGENT_NAME = 32
_SLOT = re.compile(r"^(?:hdr_)?p([1-9])(?:_|$)")
_SEPARATORS = re.compile(r"[^a-z0-9]+")
_CANONICAL_ROLES = {
    "orchestrator": "orchestrator",
    "implementation": "impl",
    "worker": "impl",
    "integration_owner": "integration_owner",
    "integration_reviewer": "integration_review",
    "deployment": "deploy",
    "qc": "qc",
    "designer": "ui_review",
    "persona": "persona",
}


class NamingError(ValueError):
    pass


def normalize_slot(value: str) -> str:
    slot = str(value).upper()
    if not re.fullmatch(r"P[1-9]", slot):
        raise NamingError(f"invalid Herdr slot: {value}")
    return slot


def normalize_slug(value: str, *, fallback: str | None = None) -> str:
    slug = _SEPARATORS.sub("_", str(value).lower()).strip("_")
    if slug:
        return slug
    if fallback is not None:
        return fallback
    raise NamingError("name slug is empty")


def slot_from_agent_name(name: str | None) -> str | None:
    match = _SLOT.match(name or "")
    return f"P{match.group(1)}" if match else None


def slot_from_lane_id(lane_id: str | None) -> str | None:
    match = re.fullmatch(r"[pP]([1-9])", lane_id or "")
    return f"P{match.group(1)}" if match else None


def canonical_display_role(slot: str | None, role: str) -> str:
    del slot
    normalized = normalize_slug(role)
    return _CANONICAL_ROLES.get(normalized, normalized)


def format_agent_name(
    slot: str,
    role: str,
    task: str | None = None,
    *,
    occupied: Collection[str] = (),
    collision_key: str | None = None,
) -> str:
    prefix = normalize_slot(slot).lower()
    role_slug = normalize_slug(role)
    role_prefix = f"{prefix}_{role_slug}"
    if len(role_prefix) > MAX_AGENT_NAME:
        raise NamingError("slot and role do not fit Herdr's name limit")
    task_slug = (
        normalize_slug(task, fallback="task")
        if task is not None
        else None
    )
    candidate = role_prefix
    if task_slug is not None:
        task_budget = MAX_AGENT_NAME - len(role_prefix) - 1
        if task_budget > 0:
            candidate = f"{role_prefix}_{task_slug[:task_budget].rstrip('_')}"
    if candidate not in occupied:
        return candidate
    if not collision_key:
        raise NamingError("collision_key is required for an occupied name")
    digest = hashlib.sha256(collision_key.encode()).hexdigest()
    max_suffix = MAX_AGENT_NAME - len(role_prefix) - 1
    for suffix_length in range(4, min(len(digest), max_suffix) + 1, 2):
        suffix = digest[:suffix_length]
        head_budget = MAX_AGENT_NAME - len(suffix) - 1
        head = candidate[:head_budget].rstrip("_")
        if not head.startswith(role_prefix):
            break
        suffixed = f"{head}_{suffix}"
        if suffixed not in occupied:
            return suffixed
    raise NamingError("cannot produce a unique bounded Herdr name")


def stable_agent_identity(
    name: str | None,
    session_id: str | None,
) -> dict[str, str | None]:
    return {
        "slot": slot_from_agent_name(name),
        "session_id": session_id,
    }
