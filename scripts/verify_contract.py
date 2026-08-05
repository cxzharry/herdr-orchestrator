#!/usr/bin/env python3
"""Verify the simplified fixed-role Herdr contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_REFERENCES = (
    "references/plan-contract.md",
    "references/routing.md",
    "references/git-integration.md",
    "references/review-deploy.md",
    "references/high-assurance.md",
    "references/delivery-flow.md",
)
REQUIRED_RUNTIME = (
    "scripts/herdr_identity.py",
    "scripts/workspace_state.py",
    "scripts/manage_worker_pool.py",
    "scripts/controller_router.py",
    "scripts/controller_tick.py",
    "scripts/run_watcher.py",
    "scripts/render_agent_status.py",
    "scripts/write_lane_receipt.py",
    "scripts/validate_lane_receipt.py",
    "scripts/verify_complexity.py",
)
FIXED_ROLES = (
    "p1_orchestrator",
    "p2_impl",
    "p3_impl",
    "p4_impl",
    "p5_integration",
    "p6_review",
    "p7_qc",
    "p8_design",
    "p9_persona",
)
SINGLE_FUNCTION_SCENARIO = "benchmarks/scenarios/single-function-compact-v1.json"


def verify() -> dict:
    failures: list[str] = []
    skill = _read(ROOT / "SKILL.md")
    readme = _read(ROOT / "README.md")
    references = {relative: _read(ROOT / relative) for relative in REQUIRED_REFERENCES}
    corpus = _normalize("\n".join([skill, readme, *references.values()]))

    for relative in REQUIRED_REFERENCES:
        if not (ROOT / relative).is_file():
            failures.append(f"missing reference: {relative}")
        elif relative not in skill and relative != "references/delivery-flow.md":
            failures.append(f"SKILL.md must route to {relative}")
    for relative in REQUIRED_RUNTIME:
        if not (ROOT / relative).is_file():
            failures.append(f"missing runtime helper: {relative}")

    if len(skill.split()) > 350:
        failures.append("SKILL.md must contain no more than 350 words")
    for marker in (
        "approved spec and approved execution plan",
        "HERDR_ENV=1",
        "P1 is controller-only",
        "It never implements, tests, integrates, reviews, commits, pushes, or deploys",
        "A reducer return is internal",
        "Compact applies only",
        "Otherwise use Standard",
        "one to three path-owned lanes",
        "P5 integration and P6 independent QC are mandatory",
        "applicable P7, P8, and P9 lanes concurrently",
        "workspace-state.json",
    ):
        if marker not in corpus:
            failures.append(f"contract missing marker: {marker}")
    for role in FIXED_ROLES:
        if role not in corpus:
            failures.append(f"missing fixed role: {role}")

    routing = references["references/routing.md"]
    for marker in (
        "same Herdr workspace lacks a live controller",
        "forward immutable requests",
        "first prompt creates",
        "same-session move",
        "foreign workspace session is never adopted",
        "three misses",
        "never close user panes",
        "ownership queue",
        "capacity queue",
        "watcher.wake_verified_at",
    ):
        if marker not in _normalize(routing):
            failures.append(f"routing missing marker: {marker}")

    readme_required = (
        "The Superpowers baselines are frozen reference values",
        "only the Herdr candidate is rerun",
        "beats 152s on Compact and 1009s",
    )
    for marker in readme_required:
        if marker not in readme:
            failures.append(f"README missing marker: {marker}")

    scenario_path = ROOT / SINGLE_FUNCTION_SCENARIO
    if not scenario_path.is_file():
        failures.append(f"missing scenario: {SINGLE_FUNCTION_SCENARIO}")
    else:
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        if scenario.get("mode") != "Compact":
            failures.append("single-function scenario must use Compact")
        if scenario.get("mutate_baseline") is not False:
            failures.append("single-function scenario must not mutate baseline")
        _verify_single_function_fixture(scenario, failures)
        if not scenario.get("timing", {}).get("start") or not scenario.get(
            "timing", {}
        ).get("stop"):
            failures.append("single-function scenario must define timing bounds")

    return {
        "status": "pass" if not failures else "fail",
        "skill_words": len(skill.split()),
        "references": list(REQUIRED_REFERENCES),
        "failures": failures,
    }


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _verify_single_function_fixture(scenario: dict, failures: list[str]) -> None:
    fixture = scenario.get("fixture")
    if not isinstance(fixture, dict):
        failures.append("single-function scenario must define fixture")
        return

    if fixture.get("base_kind") != "candidate-relative-git-blob":
        failures.append(
            "single-function fixture base_kind must be candidate-relative-git-blob"
        )
    if not fixture.get("base_sha"):
        failures.append("single-function fixture must define base_sha")
    if not fixture.get("sha256"):
        failures.append("single-function scenario must lock fixture sha256")

    source_relative = fixture.get("source_path")
    source = _candidate_relative_path(source_relative)
    if source is None:
        failures.append("single-function fixture must define candidate-relative source_path")
        return
    if not source.is_file():
        failures.append(f"missing single-function fixture source: {source_relative}")
        return

    content = source.read_bytes()
    source_sha256 = hashlib.sha256(content).hexdigest()
    if fixture.get("sha256") != source_sha256:
        failures.append("single-function fixture sha256 mismatch")
    blob = b"blob " + str(len(content)).encode("ascii") + b"\0" + content
    if fixture.get("base_sha") != hashlib.sha1(blob).hexdigest():
        failures.append("single-function fixture base_sha mismatch")

    files = fixture.get("files")
    if not isinstance(files, list) or not files:
        failures.append("single-function fixture must define materialized files")
        return
    for item in files:
        target = item.get("path") if isinstance(item, dict) else None
        if not target:
            failures.append("single-function fixture file must define path")
            continue
        if item.get("source_path") != source_relative:
            failures.append(f"single-function fixture source mismatch: {target}")
        if item.get("sha256") != source_sha256:
            failures.append(f"single-function fixture digest mismatch: {target}")


def _candidate_relative_path(relative: object) -> Path | None:
    if not isinstance(relative, str) or not relative:
        return None
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        return None
    return ROOT / path


def main() -> int:
    result = verify()
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
