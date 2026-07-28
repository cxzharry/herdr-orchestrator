#!/usr/bin/env python3
"""Deterministically render the canonical SVG to PNG with pinned local tools."""

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, __version__ as pillow_version


SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = SKILL_ROOT / "assets"
MANIFEST = ASSET_DIR / "manifest.json"


def toolchain() -> tuple[str, str]:
    chrome = shutil.which("google-chrome")
    if not chrome:
        mac_chrome = Path(
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        )
        chrome = str(mac_chrome) if mac_chrome.is_file() else None
    if not chrome:
        raise RuntimeError("google-chrome is required")
    version = subprocess.run(
        [chrome, "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return chrome, version


def render(output: Path) -> None:
    manifest = json.loads(MANIFEST.read_text())
    renderer = manifest["renderer"]
    chrome, chrome_version = toolchain()
    if chrome_version != renderer["chrome"] or pillow_version != renderer["pillow"]:
        raise RuntimeError(
            f"renderer drift: chrome={chrome_version!r}, pillow={pillow_version!r}"
        )

    svg = ASSET_DIR / manifest["render_source"]
    source_size = tuple(renderer["source_size"])
    output_size = tuple(renderer["output_size"])
    with tempfile.TemporaryDirectory() as temp_name:
        temp = Path(temp_name)
        screenshot = temp / "full.png"
        profile = temp / "chrome-profile"
        try:
            subprocess.run(
                [
                    chrome,
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--hide-scrollbars",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--force-device-scale-factor=1",
                    f"--user-data-dir={profile}",
                    f"--window-size={source_size[0]},{source_size[1]}",
                    f"--screenshot={screenshot}",
                    svg.resolve().as_uri(),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            if not screenshot.is_file() or screenshot.stat().st_size == 0:
                raise
        with Image.open(screenshot) as image:
            rendered = image.convert("RGB").resize(
                output_size,
                Image.Resampling.LANCZOS,
            )
            rendered.save(output, format="PNG", compress_level=9)


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", type=Path)
    action.add_argument("--check", type=Path)
    args = parser.parse_args()

    if args.write:
        render(args.write.resolve())
        print(args.write.resolve())
        return 0

    with tempfile.TemporaryDirectory() as temp_name:
        candidate = Path(temp_name) / "rendered.png"
        render(candidate)
        if candidate.read_bytes() != args.check.read_bytes():
            with Image.open(candidate) as rendered, Image.open(args.check) as expected:
                mismatch = ImageChops.difference(
                    rendered.convert("RGB"),
                    expected.convert("RGB"),
                ).getbbox()
            print(f"byte mismatch; pixel_bbox={mismatch}")
            return 1
    print("exact render match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
