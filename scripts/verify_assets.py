#!/usr/bin/env python3
"""Verify the simplified delivery graph asset bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"
DEFAULT_MANIFEST = ASSET_DIR / "manifest.json"
REQUIRED_FILES = {
    "delivery-flow.excalidraw",
    "delivery-flow.svg",
    "delivery-flow.png",
}
REQUIRED_TEXT = (
    "Approved plan",
    "P1 claim or same-workspace forward",
    "atomic controller tick",
    "P2/P3/P4 fixed warm implementation slots",
    "ownership queue / capacity queue",
    "immutable receipts",
    "Compact verifier OR Standard P5 integration",
    "P6 review -> conditional P7/P8/P9",
    "P5 install/push/deploy",
    "Herdr live state -> workspace watcher -> event queue -> P1 wake",
    "workspace-state.json -> controller tick",
    "p1_orchestrator",
    "p2_impl",
    "p3_impl",
    "p4_impl",
    "p5_integration",
    "p6_review",
    "p7_qc",
    "p8_design",
    "p9_persona",
    "foreign workspace never adopted",
    "never close user panes",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def verify(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    files = set(manifest.get("sha256", {}))
    if files != REQUIRED_FILES:
        failures.append("manifest must hash the canonical Excalidraw, SVG, and PNG")
    for name in REQUIRED_FILES:
        path = ASSET_DIR / name
        if not path.is_file():
            failures.append(f"missing asset: {name}")
        elif manifest.get("sha256", {}).get(name) != digest(path):
            failures.append(f"sha256 mismatch: {name}")

    excalidraw_text = _normalize(_excalidraw_text(ASSET_DIR / "delivery-flow.excalidraw"))
    svg_text = _normalize(_svg_text(ASSET_DIR / "delivery-flow.svg"))
    for marker in REQUIRED_TEXT:
        normalized_marker = _normalize(marker)
        if normalized_marker not in excalidraw_text:
            failures.append(f"Excalidraw missing text: {marker}")
        if normalized_marker not in svg_text:
            failures.append(f"SVG missing text: {marker}")

    png_path = ASSET_DIR / "delivery-flow.png"
    if png_path.is_file():
        with png_path.open("rb") as stream:
            header = stream.read(24)
        if (
            len(header) != 24
            or header[:8] != b"\x89PNG\r\n\x1a\n"
            or struct.unpack(">II", header[16:24]) != (3000, 1113)
        ):
            failures.append("PNG must be 3000x1113")

    return {
        "status": "pass" if not failures else "fail",
        "assets": sorted(REQUIRED_FILES),
        "failures": failures,
    }


def _excalidraw_text(path: Path) -> str:
    document = json.loads(path.read_text(encoding="utf-8"))
    return "\n".join(
        element.get("text", "")
        for element in document.get("elements", [])
        if element.get("type") == "text" and not element.get("isDeleted")
    )


def _svg_text(path: Path) -> str:
    root = ET.parse(path).getroot()
    return "\n".join(root.itertext())


def _normalize(text: str) -> str:
    return " ".join(text.split())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    result = verify(args.manifest.resolve())
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
