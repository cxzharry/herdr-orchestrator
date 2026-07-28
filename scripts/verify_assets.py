#!/usr/bin/env python3
"""Verify the immutable graph bundle and eight-pane Excalidraw invariants."""

import argparse
import hashlib
import json
import re
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
    "delivery-flow.excalidraw": "16e572aab97afa42e0443dc71c98f80561e76b6375275769b007067ca2cc326b",
    "delivery-flow.svg": "8ab9b4b5d007f24f5f5ab08ad2443c02bcd7bf2f2daa7bb8901c668a4a89f395",
}
PANE_IDS = (
    "orchestrator",
    "worker_1",
    "worker_2",
    "worker_3",
    "worker_4",
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
    "qc_gate",
    "ux_gate",
    "verified",
    "end",
}
EXPECTED_EDGES = {
    ("task", "orchestrator"),
    ("orchestrator", "ready"),
    ("ready", "contract"),
    ("ready", "orchestrator"),
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
    ("integrated", "qc"),
    ("qc", "qc_gate"),
    ("qc_gate", "designer"),
    ("qc_gate", "orchestrator"),
    ("designer", "persona"),
    ("persona", "ux_gate"),
    ("ux_gate", "verified"),
    ("verified", "end"),
    ("ux_gate", "orchestrator"),
}
ARROW_IDS = {
    "task_o",
    "o_ready",
    "ready_yes",
    "ready_no",
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
    "integrated_qc",
    "qc_gate_edge",
    "qc_yes",
    "qc_no",
    "designer_persona",
    "persona_ux",
    "ux_yes",
    "verified_end",
    "ux_no",
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
    "qc": "rectangle",
    "qc_gate": "diamond",
    "designer": "rectangle",
    "persona": "rectangle",
    "ux_gate": "diamond",
    "verified": "rectangle",
    "end": "ellipse",
}
EXPECTED_TEXTS = {
    "task_text": "USER\nTASK",
    "orchestrator_text": "P1  ORCHESTRATOR\n\nplan · route · state\nnever self-approve",
    "ready_text": "Ready?\nClear + testable?",
    "contract_text": "EXECUTION CONTRACT\n\nsource · ownership\ndependencies · checks\nDone criteria",
    "isolation_text": "Need\nisolation?",
    "worktree_text": "WORKTREE / LANE\nbranch · port · state",
    "fork_text": "",
    "worker_1_text": "P2  WORKER 1\nLane A",
    "worker_2_text": "P3  WORKER 2\nLane B",
    "worker_3_text": "P4  WORKER 3\nLane C",
    "worker_4_text": "P5  WORKER 4\nLane D / E2E + SMOKE",
    "worker_4_badge_text": "INTEGRATION OWNER",
    "integrated_text": "INTEGRATED BUILD\n\none mutator · merge\nfull checks · local seed",
    "qc_text": "P6  QC\n\nregression · contract\nPlaywright · evidence",
    "qc_badge_text": "INTEGRATION REVIEWER",
    "qc_gate_text": "Regression\npass?",
    "designer_text": "P7  DESIGNER\n\nUI · UX · responsive\nvisual feedback",
    "persona_text": "P8  PERSONA\n\nreal journey · friction\nexperience feedback",
    "ux_gate_text": "Experience\npass?",
    "verified_text": "VERIFIED DELIVERY\n\nevidence complete",
    "end_text": "END",
    "ready_yes_label": "yes",
    "ready_no_label": "no · clarify",
    "isolation_no_label": "no · shared tree + ownership",
    "isolation_yes_label": "yes · overlap / risky",
    "qc_yes_label": "yes",
    "qc_no_label": "no · route to owning worker",
    "ux_yes_label": "yes",
    "ux_no_label": "no · UX/persona findings → owning worker",
    "title": "8-PANE MULTI-AGENT DELIVERY LOOP",
    "subtitle": "P1 Orchestrator · P2–P5 Workers · P6 QC · P7 Designer · P8 Persona",
    "legend": "GREEN = ORCHESTRATOR   WHITE = OTHER AGENT   VIOLET BADGE = SECOND ROLE, SAME PANE",
    "phase_1": "1  PLAN + CONTRACT",
    "phase_2": "2  PARALLEL WORK",
    "phase_3": "3  ONE PLAYWRIGHT SLOT: P5 SMOKE → QC → DESIGNER → PERSONA",
}
AGENT_TEXT_IDS = {
    "orchestrator_text",
    "worker_1_text",
    "worker_2_text",
    "worker_3_text",
    "worker_4_text",
    "qc_text",
    "designer_text",
    "persona_text",
}
EXPECTED_ELEMENT_TYPES = {
    **EXPECTED_NODE_TYPES,
    **{text_id: "text" for text_id in EXPECTED_TEXTS},
    **{arrow_id: "arrow" for arrow_id in ARROW_IDS},
    "worker_4_badge": "rectangle",
    "qc_badge": "rectangle",
}


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
        detected_agent_text_ids = {
            item.get("id")
            for item in elements
            if item.get("type") == "text"
            and item.get("id") != "subtitle"
            and re.search(
                r"\bP\d+\s+(?:ORCHESTRATOR|WORKER|QC|DESIGNER|PERSONA)\b",
                item.get("text", ""),
            )
        }
        if detected_agent_text_ids != AGENT_TEXT_IDS:
            failures.append("graph must contain exactly the canonical eight agent labels")

        badges = {
            text for text in texts if text in {"INTEGRATION OWNER", "INTEGRATION REVIEWER"}
        }
        if badges != {"INTEGRATION OWNER", "INTEGRATION REVIEWER"}:
            failures.append("dual-role badges must be Integration Owner and Integration Reviewer")
        if len(arrows) != 25:
            failures.append(f"expected 25 arrows, found {len(arrows)}")
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    result = verify(args.manifest.resolve())
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
