#!/usr/bin/env python3
"""Verify the concise nine-pane Herdr routing contract."""

import json
import re
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL = SKILL_ROOT / "SKILL.md"
AGENT_METADATA = SKILL_ROOT / "agents" / "openai.yaml"
POOL_HELPER = SKILL_ROOT / "scripts" / "manage_worker_pool.py"
RECEIPT_WAITER = SKILL_ROOT / "scripts" / "await_receipts.py"
STATE_UPDATER = SKILL_ROOT / "scripts" / "set_lane_state.py"
STATE_CREATOR = SKILL_ROOT / "scripts" / "create_control_state.py"
RECEIPT_WRITER = SKILL_ROOT / "scripts" / "write_lane_receipt.py"
LANE_REGISTRAR = SKILL_ROOT / "scripts" / "register_lane.py"

EXPECTED_PANES = {
    "P1": ("Orchestrator", "gpt-5.6-sol", "high"),
    "P2": ("Worker 1", "gpt-5.5", "medium"),
    "P3": ("Worker 2", "gpt-5.5", "medium"),
    "P4": ("Worker 3", "gpt-5.5", "medium"),
    "P5": ("Worker 4, then Integration Owner", "gpt-5.5", "high"),
    "P6": ("Integration Reviewer", "gpt-5.5", "high"),
    "P7": ("QC", "gpt-5.5", "high"),
    "P8": ("Designer", "gpt-5.5", "high"),
    "P9": ("Persona", "gpt-5.5", "medium"),
}
REQUIRED_REFERENCES = {
    "references/routing.md",
    "references/git-integration.md",
    "references/review-deploy.md",
    "references/high-assurance.md",
}
LANE_BRIEF_FIELDS = {
    "ROLE",
    "GOAL",
    "REQUIRED EVENT SKILLS",
    "CONTRACT / LANE / GENERATION",
    "INPUT IDENTITY",
    "OWNED SCOPE",
    "PREREQUISITES",
    "ACCEPTANCE",
    "TERMINAL CHECKS",
    "RECEIPT PATH",
    "DO NOT",
    "STOP / ESCALATE WHEN",
}
REQUIRED_SKILLS = {
    "test-driven-development",
    "systematic-debugging",
    "using-git-worktrees",
    "receiving-code-review",
    "verification-before-completion",
    "finishing-a-development-branch",
}
FORBIDDEN_RUNTIME_SKILLS = {
    "brainstorming",
    "writing-plans",
    "dispatching-parallel-agents",
    "subagent-driven-development",
    "executing-plans",
    "requesting-code-review",
}


def parse_roster(markdown: str) -> dict[str, tuple[str, str, str]]:
    rows = {}
    pattern = re.compile(
        r"^\|\s*(P\d+)\s*\|\s*([^|]+?)\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|$",
        re.MULTILINE,
    )
    for pane, role, model, effort in pattern.findall(markdown):
        rows[pane] = (role.strip(), model, effort)
    return rows


def verify() -> dict:
    failures = []
    skill = SKILL.read_text(encoding="utf-8") if SKILL.is_file() else ""
    metadata = (
        AGENT_METADATA.read_text(encoding="utf-8")
        if AGENT_METADATA.is_file()
        else ""
    )
    reference_text = {}

    roster = parse_roster(skill)
    if roster != EXPECTED_PANES:
        failures.append("model roster must match the canonical P1-P9 contract")

    for relative in sorted(REQUIRED_REFERENCES):
        path = SKILL_ROOT / relative
        if not path.is_file():
            failures.append(f"missing conditional reference: {relative}")
            continue
        reference_text[relative] = path.read_text(encoding="utf-8")
        if relative not in skill:
            failures.append(f"SKILL.md must route to {relative}")

    if "references/runtime-contract.md" in skill:
        failures.append("SKILL.md must not require the monolithic runtime contract")
    if len(skill.split()) > 350:
        failures.append("SKILL.md must contain no more than 350 words")
    if not POOL_HELPER.is_file():
        failures.append("missing deterministic worker-pool helper")
    if not RECEIPT_WAITER.is_file():
        failures.append("missing deterministic receipt waiter")
    if not STATE_UPDATER.is_file():
        failures.append("missing atomic lane-state updater")
    if not STATE_CREATOR.is_file():
        failures.append("missing deterministic control-state creator")
    if not RECEIPT_WRITER.is_file():
        failures.append("missing deterministic terminal receipt writer")
    if not LANE_REGISTRAR.is_file():
        failures.append("missing atomic on-demand lane registrar")

    routing = reference_text.get("references/routing.md", "")
    for field in sorted(LANE_BRIEF_FIELDS):
        if field not in routing:
            failures.append(f"routing brief is missing field: {field}")
    for skill_name in sorted(REQUIRED_SKILLS):
        if skill_name not in skill and skill_name not in routing:
            failures.append(f"missing required skill route: {skill_name}")

    forbidden_marker = "Never invoke these inside Herdr:"
    if forbidden_marker not in routing:
        failures.append("routing must declare the nested-scheduler prohibition")
    for skill_name in sorted(FORBIDDEN_RUNTIME_SKILLS):
        if skill_name not in routing:
            failures.append(f"routing must forbid nested skill: {skill_name}")

    review = " ".join(
        reference_text.get("references/review-deploy.md", "").split()
    )
    deployment_markers = {
        "artifact generation": "artifact generation",
        "staged": "dev + main/production",
        "single": "single environment",
        "local": "no deployment target",
        "parallel": "P7, P8, and P9 run concurrently",
        "applicability": "start only applicable review",
        "stale receipt": "old tuple-bound PASS receipts",
        "isolated": "separate runtime, tenant, seed, browser profile, and lock",
        "roles": "all applicable system roles",
        "mock": "deterministic mock data",
        "recovery": "rollback or fix-forward",
    }
    for name, marker in deployment_markers.items():
        if marker not in review:
            failures.append(f"review/deploy contract is missing {name}: {marker}")
    if "P7 is always blocking" in review:
        failures.append("P7 must be blocking only when its approved matrix applies")

    stale_runtime_markers = {
        "full brainstorming workflow on every run",
        "| P1 design |",
        "| P1 after design approval |",
    }
    for marker in sorted(stale_runtime_markers):
        if marker in routing:
            failures.append(f"routing contains superseded runtime behavior: {marker}")

    routing = " ".join(routing.split())
    routing_markers = {
        "approved input": "approved spec and approved execution plan",
        "control state": "control-state.json",
        "direct identity": "agent_name, pane_id, and session_id",
        "generation": "generation",
        "yolo launch": "-- --yolo",
        "worker model": "--model gpt-5.5",
        "effort": "model_reasoning_effort",
        "prompt capsule": "prompt capsule",
        "capsule budget": "1,500 bytes",
        "report budget": "20 lines",
        "explicit references": "predicates are explicitly true",
        "scoped MCP": "mcp_servers.<name>.enabled=false",
        "no benchmark contamination": "Do not inspect prior benchmark answers",
        "false predicate": "Loading a false-predicate reference is a contract failure",
        "compact gate": "## Compact gate",
        "worker reuse policy": "## Worker reuse policy",
        "reuse is internal": "Worker reuse is not a delivery gate",
        "pool prepare": "manage_worker_pool.py prepare --contract-id",
        "pool bind": "manage_worker_pool.py bind --contract-id",
        "pool ready": "startup/trust gates are cleared",
        "reuse lease": "lease_id",
        "reuse reset": "/new",
        "reuse same-contract": "same approved delivery contract",
        "reuse cold fallback": "cold-start the lane",
        "compact topology": "P1 -> ready P2/P3/P4 workers in parallel",
        "compact receipt": "COMPACT PASS",
        "compact receipt budget": "600 bytes",
        "compact reviewer skip": "Do not start P5-P9",
        "compact no files": "Do not create a run directory",
        "compact preflight": "Compact preflight is limited",
        "compact no help": "Do not run broad CLI help",
        "compact tail": "--source recent-unwrapped --lines 12",
        "compact no logs": "Do not load full terminal history",
        "compact upgrade": "upgrades the run to the standard gate",
        "single-worker fast path": "P1 -> P2 -> P5 Integration Owner",
        "no P7 substitution": "Do not substitute P7 for P5 or P6",
        "targeted wait": "wait only on the lane",
        "receipt waiter": "await_receipts.py",
        "live receipt watchdog": "tracks live session identity",
        "moved pane rebind": "same session_id appears under a new pane_id",
        "lost exit": "status=lost and exit code 2",
        "no lost timeout": "Do not wait for the receipt timeout",
        "no chat wait": "Do not call `herdr agent wait` after dispatch",
        "atomic state": "set_lane_state.py",
        "state creator": "create_control_state.py",
        "receipt writer": "write_lane_receipt.py",
        "lane registrar": "register_lane.py",
        "no handcrafted state": "Do not handcraft control-state JSON",
        "no handcrafted receipts": "Never ask a worker to handcraft receipt JSON",
        "absolute input": "approved input's absolute path and digest",
        "new owned paths": "intentionally new path is not a blocker",
        "no memory search": "do not search memory, history, or prior runs",
        "acceptance first": "read that exact harness before writing RED tests",
        "parallel integration prep": "same fan-out boundary as P2-P4",
        "deep immutability": "constructor-supplied collection",
        "no prompt waits": "Submit independent lane prompts without `--wait`",
        "receipt completion": "terminal receipt is the completion signal",
        "busy retry": "agent_pane_busy",
        "prompt delivery": "first submitted prompt does not appear",
        "terminal receipts": "terminal receipts",
        "compact evidence": "path and digest",
        "P5 restart": "P5 must restart",
        "parallel integration": "P5 smoke and P6 review run concurrently",
        "bounded blocker": "same blocker twice",
    }
    for name, marker in routing_markers.items():
        if marker not in routing:
            failures.append(f"routing contract is missing {name}: {marker}")
    for stale_marker in ("## Warm lane pool", "token delta", "runtime telemetry", "`/status`"):
        if stale_marker in routing:
            failures.append(f"routing contains removed critical-path behavior: {stale_marker}")

    metadata_markers = {
        'short_description: "Run Herdr delivery from approved plan to deploy"',
        "directly controllable Herdr lanes",
    }
    for marker in metadata_markers:
        if marker not in metadata:
            failures.append(f"agent metadata is stale: {marker}")

    return {
        "status": "pass" if not failures else "fail",
        "panes": len(roster),
        "required_references": sorted(REQUIRED_REFERENCES),
        "failures": failures,
    }


def main() -> int:
    result = verify()
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
