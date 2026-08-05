import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import verify_contract
from scripts.verify_assets import REQUIRED_TEXT


ROOT = Path(__file__).resolve().parents[1]


def normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


class P1BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.skill = normalized(ROOT / "SKILL.md")
        self.readme = normalized(ROOT / "README.md")
        self.references = {
            path.name: normalized(path) for path in sorted((ROOT / "references").glob("*.md"))
        }
        source = json.loads((ROOT / "assets" / "delivery-flow.excalidraw").read_text())
        self.asset_text = " ".join(
            " ".join(element.get("text", "").split())
            for element in source.get("elements", [])
            if element.get("type") == "text" and not element.get("isDeleted")
        )
        self.corpus = "\n".join([self.skill, self.readme, *self.references.values(), self.asset_text])

    def test_p1_boundary_forbids_delivery_actions(self):
        required = [
            "P1 is controller-only",
            "It never implements, tests, integrates, reviews, commits, pushes, or deploys",
            "P5 integrates accepted worker outputs",
            "P6 reviews",
            "P6 independent QC",
        ]
        for marker in required:
            self.assertIn(marker, self.corpus)

        forbidden_patterns = [
            r"P1\s+runs?\s+(?:product\s+)?(?:tests|builds|browser checks)",
            r"P1\s+(?:implements|tests|integrates|reviews|commits|pushes|deploys)",
            r"P1\s+->[^\\n]+->\s*P1\s+reruns",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, self.corpus, flags=re.IGNORECASE), pattern)

    def test_fixed_roles_and_single_ledger_are_visible(self):
        for marker in [
            "p1_orchestrator",
            "p2_impl",
            "p3_impl",
            "p4_impl",
            "workspace-state.json",
            "ownership queue",
            "capacity queue",
            "watcher",
        ]:
            self.assertIn(marker, self.corpus)

    def test_dispatch_stall_rules_are_enforceable(self):
        for marker in [
            "dispatch independent briefs concurrently",
            "prewarm P5/P6 while P2-P4 work",
            "redirect at 60s without observable progress",
            "reassign at 120s without resetting the timer",
            "review completed lane diffs while siblings run",
            "prevent duplicate writes during reassignment",
        ]:
            self.assertIn(marker, self.corpus)

    def test_fast_path_keeps_integration_and_independent_qc(self):
        for marker in [
            "one to three path-owned lanes",
            "P5 integration and P6 independent QC are mandatory",
            "single function or single file",
            "applicable P7, P8, and P9 lanes concurrently",
        ]:
            self.assertIn(marker, self.corpus)
        self.assertNotIn("disjoint P2-P4 paths", self.corpus)

    def test_asset_validator_requires_current_delivery_contract(self):
        required = " ".join(REQUIRED_TEXT)
        for marker in [
            "P5 integration (Compact + Standard)",
            "P6 independent QC (Compact + Standard)",
            "Standard only: applicable P7/P8/P9 concurrently",
        ]:
            self.assertIn(marker, required)
        self.assertNotIn("Compact verifier", required)
        self.assertNotIn("conditional P7/P8/P9", required)

    def test_graph_shows_required_flow(self):
        for marker in [
            "Approved plan",
            "P1 claim or same-workspace forward",
            "atomic controller tick",
            "P2/P3/P4 fixed warm implementation slots",
            "immutable receipts",
            "P5 integration (Compact + Standard)",
            "P6 independent QC (Compact + Standard)",
            "Standard only: applicable P7/P8/P9 concurrently",
            "P5 install/push/deploy",
            "Herdr live state -> workspace watcher -> event queue -> P1 wake",
            "never close user panes",
        ]:
            self.assertIn(marker, self.asset_text)

        for obsolete in [
            "Compact verifier",
            "Compact PASS",
            "no P5-P9",
            "conditional P7/P8/P9",
        ]:
            self.assertNotIn(obsolete, self.asset_text)

        self.assertNotIn("foreign workspace adopted", self.asset_text)

    def test_single_function_fixture_is_candidate_relative_and_digest_locked(self):
        scenario = json.loads(
            (ROOT / "benchmarks/scenarios/single-function-compact-v1.json").read_text(
                encoding="utf-8"
            )
        )
        fixture = scenario["fixture"]
        self.assertEqual("candidate-relative-git-blob", fixture.get("base_kind"))
        source_path = fixture.get("source_path")
        self.assertIsInstance(source_path, str)
        source = ROOT / source_path
        self.assertTrue(source.is_file(), source)
        content = source.read_bytes()
        self.assertEqual(hashlib.sha256(content).hexdigest(), fixture.get("sha256"))
        blob = b"blob " + str(len(content)).encode("ascii") + b"\0" + content
        self.assertEqual(hashlib.sha1(blob).hexdigest(), fixture.get("base_sha"))
        self.assertEqual(
            {"public_helper.py", "verify.py"},
            {item["path"] for item in fixture.get("files", [])},
        )
        for item in fixture["files"]:
            self.assertEqual(source_path, item.get("source_path"))
            self.assertEqual(fixture["sha256"], item.get("sha256"))

    def test_contract_verifier_rejects_missing_single_function_fixture_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_probe_scenario(root)
            with patch.object(verify_contract, "ROOT", root):
                failures = verify_contract.verify()["failures"]

        self.assertIn(
            "missing single-function fixture source: "
            "benchmarks/fixtures/single-function-compact-v1/public_helper.py",
            failures,
        )

    def test_contract_verifier_rejects_fixture_digest_and_base_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_probe_scenario(root)
            source = (
                root
                / "benchmarks/fixtures/single-function-compact-v1/public_helper.py"
            )
            source.parent.mkdir(parents=True)
            source.write_text("drift\n", encoding="utf-8")
            with patch.object(verify_contract, "ROOT", root):
                failures = verify_contract.verify()["failures"]

        self.assertIn("single-function fixture sha256 mismatch", failures)
        self.assertIn("single-function fixture base_sha mismatch", failures)

    @staticmethod
    def _write_probe_scenario(root: Path) -> None:
        scenario = root / "benchmarks/scenarios/single-function-compact-v1.json"
        scenario.parent.mkdir(parents=True)
        scenario.write_text(
            json.dumps(
                {
                    "mode": "Compact",
                    "mutate_baseline": False,
                    "fixture": {
                        "base_kind": "candidate-relative-git-blob",
                        "base_sha": "0" * 40,
                        "source_path": (
                            "benchmarks/fixtures/single-function-compact-v1/"
                            "public_helper.py"
                        ),
                        "sha256": "0" * 64,
                        "files": [],
                    },
                    "timing": {"start": "start", "stop": "stop"},
                }
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
