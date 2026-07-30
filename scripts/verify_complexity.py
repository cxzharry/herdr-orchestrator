#!/usr/bin/env python3
"""Release complexity gates for the simplified Herdr runtime."""

from __future__ import annotations

import json
from pathlib import Path


SUPERSEDED_FILES = (
    "scripts/runtime_registry.py",
    "scripts/test_runtime_registry.py",
    "scripts/assign_agent_name.py",
    "scripts/test_assign_agent_name.py",
    "scripts/agent_naming.py",
    "scripts/test_agent_naming.py",
    "scripts/await_receipts.py",
    "scripts/test_await_receipts.py",
    "scripts/next_controller_action.py",
    "scripts/test_next_controller_action.py",
    "scripts/scheduler_state.py",
    "scripts/test_scheduler_state.py",
)
STATE_PRIMITIVES = ("fcntl.flock", "tempfile.mkstemp", "os.replace")
DOC_FORBIDDEN = (
    "runtime-registry",
    "task_slug",
    "rename before prompt",
    "legacy rename migration",
)
COMPACT_FORBIDDEN = (
    "references/high-assurance.md",
    "references/review-deploy.md",
)


def verify(root: Path) -> dict:
    root = root.resolve()
    errors: list[str] = []
    for relative in SUPERSEDED_FILES:
        if (root / relative).exists():
            errors.append(f"superseded file remains: {relative}")

    _check_identity_owner(root, errors)
    _check_state_owner(root, errors)
    _check_docs(root, errors)

    skill_text = _read(root / "SKILL.md")
    skill_words = len(skill_text.split())
    if skill_words > 350:
        errors.append("SKILL.md must contain no more than 350 words")
    return {"status": "pass" if not errors else "fail", "errors": errors, "skill_words": skill_words}


def _check_identity_owner(root: Path, errors: list[str]) -> None:
    offenders = []
    for path in _production_scripts(root):
        if path.name == "herdr_identity.py":
            continue
        text = _read(path)
        if "agent_session" in text and "agent_identity(" not in text:
            offenders.append(_rel(root, path))
    if offenders:
        errors.append("agent_session parsed outside herdr_identity.py: " + ", ".join(offenders))


def _check_state_owner(root: Path, errors: list[str]) -> None:
    for path in _production_scripts(root):
        if path.name in {"workspace_state.py", "verify_complexity.py"}:
            continue
        text = _read(path)
        for marker in STATE_PRIMITIVES:
            if marker in text:
                errors.append(f"mutable state primitive outside workspace_state.py: {_rel(root, path)}:{marker}")


def _check_docs(root: Path, errors: list[str]) -> None:
    docs = [root / "SKILL.md", root / "README.md", *sorted((root / "references").glob("*.md"))]
    for path in docs:
        text = _read(path)
        lowered = text.lower()
        for marker in DOC_FORBIDDEN:
            if marker in lowered:
                errors.append(f"active runtime doc contains {marker}: {_rel(root, path)}")

    routing = _read(root / "references" / "routing.md")
    if "await_receipts" in routing:
        errors.append("routing references await_receipts")
    compact = _compact_section(routing)
    for marker in COMPACT_FORBIDDEN:
        if marker in compact:
            errors.append(f"Compact routing links Standard-only reference: {marker}")


def _compact_section(text: str) -> str:
    if "## Compact" not in text:
        return ""
    section = text.split("## Compact", 1)[1]
    if "\n## " in section:
        section = section.split("\n## ", 1)[0]
    return section


def _production_scripts(root: Path) -> list[Path]:
    return [
        path for path in sorted((root / "scripts").glob("*.py"))
        if not path.name.startswith("test_")
    ]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root))


def main() -> int:
    report = verify(Path("."))
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
