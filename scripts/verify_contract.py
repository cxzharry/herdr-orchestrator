#!/usr/bin/env python3
"""Verify the concise nine-pane Herdr routing contract."""

import json
import re
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL = SKILL_ROOT / "SKILL.md"
AGENT_METADATA = SKILL_ROOT / "agents" / "openai.yaml"

EXPECTED_PANES = {
    "P1": ("Orchestrator", "gpt-5.6-sol", "high"),
    "P2": ("Worker 1", "gpt-5.5", "medium"),
    "P3": ("Worker 2", "gpt-5.5", "medium"),
    "P4": ("Worker 3", "gpt-5.5", "medium"),
    "P5": ("Worker 4, then Integration Owner", "gpt-5.6-sol", "high"),
    "P6": ("Integration Reviewer", "gpt-5.6-sol", "high"),
    "P7": ("QC", "gpt-5.6-sol", "high"),
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
    "REQUIRED SKILLS",
    "INPUTS / BASE SHA / ARTIFACT DIGEST",
    "WRITABLE PATHS",
    "PREREQUISITES",
    "DONE EVIDENCE",
    "DO NOT",
    "STOP / ESCALATE WHEN",
}
REQUIRED_SKILLS = {
    "superpowers:brainstorming",
    "superpowers:writing-plans",
    "superpowers:test-driven-development",
    "superpowers:systematic-debugging",
    "superpowers:using-git-worktrees",
    "superpowers:receiving-code-review",
    "superpowers:verification-before-completion",
    "superpowers:finishing-a-development-branch",
}
FORBIDDEN_RUNTIME_SKILLS = {
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

    review = reference_text.get("references/review-deploy.md", "")
    deployment_markers = {
        "staged": "dev + main/production",
        "single": "single environment",
        "local": "no deployment target",
        "parallel": "P7, P8, and P9 run concurrently",
        "isolated": "separate runtime, tenant, seed, browser profile, and lock",
        "roles": "all applicable system roles",
        "mock": "deterministic mock data",
        "recovery": "rollback or fix-forward",
    }
    for name, marker in deployment_markers.items():
        if marker not in review:
            failures.append(f"review/deploy contract is missing {name}: {marker}")

    routing_markers = {
        "full brainstorm": "full brainstorming workflow on every run",
        "P5 restart": "P5 must restart",
        "parallel integration": "P5 smoke and P6 review run concurrently",
        "bounded blocker": "same blocker twice",
    }
    for name, marker in routing_markers.items():
        if marker not in routing:
            failures.append(f"routing contract is missing {name}: {marker}")

    metadata_markers = {
        'short_description: "Run fast nine-pane Herdr delivery loops"',
        "event-driven integration, deployment, and parallel review",
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
