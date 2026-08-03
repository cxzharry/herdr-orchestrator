import json
import re
import unittest
from pathlib import Path


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
            "Compact verifier",
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

    def test_graph_shows_required_flow(self):
        for marker in [
            "Approved plan",
            "P1 claim or same-workspace forward",
            "atomic controller tick",
            "P2/P3/P4 fixed warm implementation slots",
            "immutable receipts",
            "Compact verifier OR Standard P5 integration",
            "P6 review -> conditional P7/P8/P9",
            "P5 install/push/deploy",
            "Herdr live state -> workspace watcher -> event queue -> P1 wake",
            "never close user panes",
        ]:
            self.assertIn(marker, self.asset_text)

        self.assertNotIn("foreign workspace adopted", self.asset_text)


if __name__ == "__main__":
    unittest.main()
