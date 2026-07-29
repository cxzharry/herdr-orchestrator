#!/usr/bin/env python3
"""Verify the immutable graph bundle and nine-pane Excalidraw invariants."""

import argparse
import hashlib
import json
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = SKILL_ROOT / "assets"
DEFAULT_MANIFEST = ASSET_DIR / "manifest.json"
REQUIRED_FILES = {
    "delivery-flow.excalidraw",
    "delivery-flow.png",
    "delivery-flow.svg",
}
CANONICAL_SOURCE_HASHES = {
    "delivery-flow.excalidraw": "5588b11b39769c94bdadb8be7ac4728c41e8943ad7673e9d14358de93bf6a117",
    "delivery-flow.svg": "8ec43a5240875faaf3fec45def10c9567ce793c11d3a675f2758781ac5671633",
}
PANE_IDS = (
    "orchestrator",
    "worker_1",
    "worker_2",
    "worker_3",
    "worker_4",
    "integration_reviewer",
    "qc",
    "designer",
    "persona",
)
FLOW_NODE_IDS = {
    "task",
    "orchestrator",
    "ready",
    "contract",
    "isolation",
    "worktree",
    "fork",
    *PANE_IDS[1:],
    "integrated",
    "smoke",
    "artifact_gate",
    "deploy",
    "review_fork",
    "review_gate",
    "promotion",
    "verified",
    "end",
}
EXPECTED_EDGES = {
    ("task", "orchestrator"),
    ("orchestrator", "ready"),
    ("ready", "contract"),
    ("ready", "orchestrator"),
    ("ready", "verified"),
    ("contract", "isolation"),
    ("isolation", "fork"),
    ("isolation", "worktree"),
    ("worktree", "fork"),
    ("fork", "worker_1"),
    ("fork", "worker_2"),
    ("fork", "worker_3"),
    ("fork", "worker_4"),
    ("worker_1", "integrated"),
    ("worker_2", "integrated"),
    ("worker_3", "integrated"),
    ("worker_4", "integrated"),
    ("integrated", "smoke"),
    ("integrated", "integration_reviewer"),
    ("smoke", "artifact_gate"),
    ("integration_reviewer", "artifact_gate"),
    ("artifact_gate", "deploy"),
    ("artifact_gate", "orchestrator"),
    ("deploy", "review_fork"),
    ("review_fork", "qc"),
    ("review_fork", "designer"),
    ("review_fork", "persona"),
    ("qc", "review_gate"),
    ("designer", "review_gate"),
    ("persona", "review_gate"),
    ("review_gate", "promotion"),
    ("review_gate", "orchestrator"),
    ("promotion", "end"),
    ("verified", "end"),
}
ARROW_IDS = {
    "task_o",
    "o_ready",
    "ready_yes",
    "ready_no",
    "ready_compact",
    "contract_isolation",
    "isolation_no",
    "isolation_yes",
    "worktree_fork",
    "fork_w1",
    "fork_w2",
    "fork_w3",
    "fork_w4",
    "w1_integrated",
    "w2_integrated",
    "w3_integrated",
    "w4_integrated",
    "integrated_smoke",
    "integrated_reviewer",
    "smoke_artifact",
    "reviewer_artifact",
    "artifact_yes",
    "artifact_no",
    "deploy_review_fork",
    "review_fork_qc",
    "review_fork_designer",
    "review_fork_persona",
    "qc_review_gate",
    "designer_review_gate",
    "persona_review_gate",
    "review_yes",
    "review_no",
    "promotion_end",
    "verified_end",
}
EXPECTED_NODE_TYPES = {
    "task": "ellipse",
    "orchestrator": "rectangle",
    "ready": "diamond",
    "contract": "rectangle",
    "isolation": "diamond",
    "worktree": "rectangle",
    "fork": "ellipse",
    "worker_1": "rectangle",
    "worker_2": "rectangle",
    "worker_3": "rectangle",
    "worker_4": "rectangle",
    "integrated": "rectangle",
    "smoke": "rectangle",
    "integration_reviewer": "rectangle",
    "artifact_gate": "diamond",
    "deploy": "rectangle",
    "review_fork": "ellipse",
    "qc": "rectangle",
    "designer": "rectangle",
    "persona": "rectangle",
    "review_gate": "diamond",
    "promotion": "rectangle",
    "verified": "rectangle",
    "end": "ellipse",
}
EXPECTED_TEXTS = {
    "task_text": "USER\nTASK",
    "orchestrator_text": "P1 CONTROL PLANE\n\nINBOX · SCHEDULER TICK\nOWNERSHIP QUEUE",
    "ready_text": "Bounded\ntick ready?",
    "contract_text": "SOCKET STATE\n\nsocket-scoped P1 inbox\nwatcher event queue",
    "isolation_text": "Need\nisolation?",
    "worktree_text": "WORKTREE / LANE\nbranch · port · state",
    "fork_text": "",
    "worker_1_text": "P2  WORKER 1\nLane A",
    "worker_2_text": "P3  WORKER 2\nLane B",
    "worker_3_text": "P4  WORKER 3\nLane C",
    "worker_4_text": "P5  WORKER 4\nLane D",
    "integrated_text": "P5 INTEGRATE + DEPLOY\n\naccepted receipts · artifact\nrelease evidence",
    "integration_badge_text": "P5  INTEGRATION OWNER",
    "smoke_text": "P5  SMOKE\ncritical journeys",
    "integration_reviewer_text": "P6  INTEGRATION REVIEWER\nGit · artifact · requirements",
    "artifact_gate_text": "Artifact\nverified?",
    "deploy_text": "P5  DEPLOY\nDEV / SOLE ENV\nor local review",
    "review_fork_text": "",
    "qc_text": "P7  QC\nregression · RBAC",
    "designer_text": "P8  DESIGNER\nUI · UX · accessibility",
    "persona_text": "P9  PERSONA\njourneys · friction",
    "review_gate_text": "Blocking gates\npass?",
    "promotion_text": "STANDARD VERIFIED\nartifact · evidence",
    "verified_text": "COMPACT VERIFIER\nscope · diff · checks\nlocal stop",
    "end_text": "END",
    "ready_yes_label": "standard",
    "ready_no_label": "blocked · queue",
    "ready_compact_label": "compact",
    "isolation_no_label": "no · shared tree + ownership",
    "isolation_yes_label": "yes · overlap / risky",
    "artifact_yes_label": "yes · deploy",
    "artifact_no_label": "no · route finding to owner",
    "review_yes_label": "yes",
    "review_no_label": "no · block or rollback",
    "title": "PERSISTENT P1 CONTROL PLANE / P2-P9 DELIVERY PLANE",
    "subtitle": "INBOX -> SCHEDULER TICK -> OWNERSHIP QUEUE -> RUN WATCHER -> ASYNC SIGNAL",
    "legend": "GREEN = CONTROL PLANE   WHITE = DELIVERY PLANE   VIOLET BADGE = SECOND ROLE, SAME PANE",
    "phase_1": "1  INBOX + CONTRACT",
    "phase_2": "2  SCHEDULER + OWNERSHIP",
    "phase_3": "3  VERIFY + DEPLOY",
    "phase_4": "4  ASYNC REVIEW SIGNALS",
    "parallel_integration": "P5 SMOKE + P6 REVIEW IN PARALLEL",
    "parallel_review": "P7 QC · P8 DESIGNER · P9 PERSONA IN PARALLEL",
    "sidecar_note": "P7-P9 PREPARE EARLY · WATCHER QUEUES DONE SIGNALS",
    "deploy_policy": "P6 PASS: P5 RELEASES DEV/SOLE ENV · MAIN WAITS FOR BLOCKING GATES",
}
AGENT_TEXT_IDS = {
    "orchestrator_text",
    "worker_1_text",
    "worker_2_text",
    "worker_3_text",
    "worker_4_text",
    "integration_reviewer_text",
    "qc_text",
    "designer_text",
    "persona_text",
}
EXPECTED_ELEMENT_TYPES = {
    **EXPECTED_NODE_TYPES,
    **{text_id: "text" for text_id in EXPECTED_TEXTS},
    **{arrow_id: "arrow" for arrow_id in ARROW_IDS},
    "integration_badge": "rectangle",
}

ORCHESTRATOR_STYLE = ("#51cf66", "#173d24")
AGENT_STYLE = ("#f1f3f5", "#111318")
DECISION_STYLE = ("#ffa94d", "#3d2a16")
EVIDENCE_STYLE = ("#74c0fc", "#18324a")
BADGE_STYLE = ("#c084fc", "#322044")
ORCHESTRATOR_NODES = {"orchestrator", "promotion"}
AGENT_NODES = {
    "worker_1",
    "worker_2",
    "worker_3",
    "worker_4",
    "integrated",
    "smoke",
    "integration_reviewer",
    "deploy",
    "qc",
    "designer",
    "persona",
}
DECISION_NODES = {"ready", "isolation", "artifact_gate", "review_gate"}
EVIDENCE_NODES = {"contract", "worktree", "verified"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def verify(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    failures = []
    pane_count = 0
    arrow_count = 0

    if manifest.get("schema_version") != 2:
        failures.append("manifest schema_version must be 2")

    expected_hashes = manifest.get("sha256", {})
    expected_files = {
        manifest.get("source"),
        manifest.get("render_source"),
        *manifest.get("derived", []),
    }
    expected_files.discard(None)
    if expected_files != REQUIRED_FILES:
        failures.append("manifest must name the canonical Excalidraw, PNG, and SVG files")
    if expected_files != set(expected_hashes):
        failures.append("manifest source/derived files must match sha256 keys")

    for name, expected in expected_hashes.items():
        path = ASSET_DIR / name
        if not path.is_file():
            failures.append(f"missing asset: {name}")
        elif digest(path) != expected:
            failures.append(f"sha256 mismatch: {name}")
    for name, expected in CANONICAL_SOURCE_HASHES.items():
        path = ASSET_DIR / name
        if not path.is_file() or digest(path) != expected:
            failures.append(f"canonical source digest drift: {name}")

    source = ASSET_DIR / manifest.get("source", "")
    render_source = ASSET_DIR / manifest.get("render_source", "")
    if render_source.is_file():
        source_digest = digest(render_source)
        derived_from = manifest.get("derived_from_render_source_sha256", {})
        if set(derived_from) != set(manifest.get("derived", [])):
            failures.append("every derived asset must declare its render-source digest")
        if any(value != source_digest for value in derived_from.values()):
            failures.append("derived assets must bind to the current SVG digest")

    png_path = ASSET_DIR / "delivery-flow.png"
    if png_path.is_file():
        with png_path.open("rb") as stream:
            header = stream.read(24)
        if (
            len(header) != 24
            or header[:8] != b"\x89PNG\r\n\x1a\n"
            or struct.unpack(">II", header[16:24]) != (3000, 1113)
        ):
            failures.append("PNG must be the canonical 3000x1113 rendering")

    svg_path = ASSET_DIR / "delivery-flow.svg"
    if svg_path.is_file():
        try:
            svg_root = ET.parse(svg_path).getroot()
            svg_text = " ".join(" ".join(svg_root.itertext()).split())
            missing_svg_text = [
                text_id
                for text_id, expected in EXPECTED_TEXTS.items()
                if " ".join(expected.split()) not in svg_text
            ]
            if missing_svg_text:
                failures.append(
                    f"SVG is missing canonical text: {', '.join(missing_svg_text)}"
                )
        except ET.ParseError:
            failures.append("SVG must be well-formed XML")

    if source.is_file():
        document = json.loads(source.read_text())
        elements = [item for item in document.get("elements", []) if not item.get("isDeleted")]
        element_ids = [item.get("id") for item in elements]
        if len(element_ids) != len(set(element_ids)):
            failures.append("every Excalidraw element ID must be unique")
        by_id = {item.get("id"): item for item in elements}
        actual_element_types = {
            item.get("id"): item.get("type")
            for item in elements
        }
        if actual_element_types != EXPECTED_ELEMENT_TYPES:
            failures.append("Excalidraw elements must match the exact canonical ID/type allowlist")
        texts = [item.get("text", "") for item in elements if item.get("type") == "text"]
        arrows = [item for item in elements if item.get("type") == "arrow"]
        arrow_count = len(arrows)

        missing_panes = [
            pane_id
            for pane_id in PANE_IDS
            if pane_id not in by_id or f"{pane_id}_text" not in by_id
        ]
        pane_count = len(PANE_IDS) - len(missing_panes)
        if missing_panes:
            failures.append(f"missing panes: {', '.join(missing_panes)}")
        missing_flow_nodes = FLOW_NODE_IDS - set(by_id)
        if missing_flow_nodes:
            failures.append(f"missing flow nodes: {', '.join(sorted(missing_flow_nodes))}")
        wrong_node_types = [
            node_id
            for node_id, expected_type in EXPECTED_NODE_TYPES.items()
            if by_id.get(node_id, {}).get("type") != expected_type
        ]
        if wrong_node_types:
            failures.append(f"wrong flow node types: {', '.join(wrong_node_types)}")
        wrong_text = [
            text_id
            for text_id, expected in EXPECTED_TEXTS.items()
            if by_id.get(text_id, {}).get("type") != "text"
            or by_id[text_id].get("text") != expected
        ]
        if wrong_text:
            failures.append(f"wrong canonical text: {', '.join(wrong_text)}")
        missing_agent_labels = AGENT_TEXT_IDS - set(by_id)
        if missing_agent_labels:
            failures.append(
                "graph must contain the canonical nine pane labels: "
                + ", ".join(sorted(missing_agent_labels))
            )

        badges = {text for text in texts if "INTEGRATION OWNER" in text}
        if badges != {"P5  INTEGRATION OWNER"}:
            failures.append("the only dual-role badge must mark P5 Integration Owner")

        style_groups = {
            "orchestrator": (ORCHESTRATOR_NODES, ORCHESTRATOR_STYLE),
            "agent": (AGENT_NODES, AGENT_STYLE),
            "decision": (DECISION_NODES, DECISION_STYLE),
            "evidence": (EVIDENCE_NODES, EVIDENCE_STYLE),
            "badge": ({"integration_badge"}, BADGE_STYLE),
        }
        for label, (node_ids, expected_style) in style_groups.items():
            wrong_style = [
                node_id
                for node_id in sorted(node_ids)
                if (
                    by_id.get(node_id, {}).get("strokeColor"),
                    by_id.get(node_id, {}).get("backgroundColor"),
                )
                != expected_style
            ]
            if wrong_style:
                failures.append(
                    f"wrong {label} color role: {', '.join(wrong_style)}"
                )

        if len(arrows) != 34:
            failures.append(f"expected 34 arrows, found {len(arrows)}")
        if any(not arrow.get("startBinding") or not arrow.get("endBinding") for arrow in arrows):
            failures.append("every arrow must bind both endpoints")
        bindings = [
            binding.get("elementId")
            for arrow in arrows
            for binding in (arrow.get("startBinding") or {}, arrow.get("endBinding") or {})
        ]
        if any(element_id not in by_id for element_id in bindings):
            failures.append("every arrow binding must target an existing element")
        actual_edges = {
            (
                arrow["startBinding"]["elementId"],
                arrow["endBinding"]["elementId"],
            )
            for arrow in arrows
            if arrow.get("startBinding") and arrow.get("endBinding")
        }
        if actual_edges != EXPECTED_EDGES:
            failures.append("directed graph edges must match the canonical topology")
        if _path_exists(actual_edges, "review_gate", "verified", blocked={"orchestrator"}):
            failures.append(
                "standard review gate must not flow through the Compact verifier"
            )
        if not _path_exists(actual_edges, "ready", "verified"):
            failures.append("scheduler gate must branch directly to Compact verifier")
        if not _path_exists(actual_edges, "verified", "end"):
            failures.append("Compact verifier must stop at verified local delivery/end")
        starts = {
            arrow["startBinding"]["elementId"]
            for arrow in arrows
            if arrow.get("startBinding")
        }
        ends = {
            arrow["endBinding"]["elementId"]
            for arrow in arrows
            if arrow.get("endBinding")
        }
        missing_outgoing = (FLOW_NODE_IDS - {"end"}) - starts
        missing_incoming = (FLOW_NODE_IDS - {"task"}) - ends
        if missing_outgoing:
            failures.append(f"flow nodes without outgoing arrows: {', '.join(sorted(missing_outgoing))}")
        if missing_incoming:
            failures.append(f"flow nodes without incoming arrows: {', '.join(sorted(missing_incoming))}")
        if any(text.strip().upper() == "GO" for text in texts):
            failures.append("GO node is forbidden")
        if "verified" not in by_id or "end" not in by_id or by_id["verified"] is by_id["end"]:
            failures.append("Verified Delivery and END must be separate nodes")

    renderer = SKILL_ROOT / "scripts" / "render_assets.py"
    if renderer.is_file() and png_path.is_file() and svg_path.is_file():
        check = subprocess.run(
            [sys.executable, str(renderer), "--check", str(png_path)],
            capture_output=True,
            text=True,
        )
        if check.returncode:
            detail = " ".join((check.stdout + check.stderr).split())
            failures.append(f"PNG render mismatch: {detail}")
    else:
        failures.append("deterministic SVG-to-PNG renderer and canonical assets are required")

    result = {
        "manifest": str(manifest_path),
        "assets": sorted(expected_files),
        "panes": pane_count,
        "arrows": arrow_count,
        "status": "pass" if not failures else "fail",
        "failures": failures,
    }
    return result


def _path_exists(
    edges: set[tuple[str, str]],
    start: str,
    end: str,
    *,
    blocked: set[str] | None = None,
) -> bool:
    blocked = blocked or set()
    frontier = [start]
    seen = set()
    while frontier:
        node = frontier.pop()
        if node in blocked:
            continue
        if node == end:
            return True
        if node in seen:
            continue
        seen.add(node)
        frontier.extend(target for source, target in edges if source == node)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    result = verify(args.manifest.resolve())
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
