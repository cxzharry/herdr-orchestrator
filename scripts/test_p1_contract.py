import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


class PersistentP1BoundaryTests(unittest.TestCase):
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

    def test_p1_boundary_forbids_product_delivery_actions(self):
        required_markers = [
            "P1 is a persistent controller only",
            "P1 never implements, tests, integrates, reviews, commits, pushes, or deploys",
            "P5 integrates accepted worker outputs",
            "P5 writes integration and deployment evidence",
            "Compact verifier",
        ]
        for marker in required_markers:
            self.assertIn(marker, self.corpus)

        forbidden_patterns = [
            r"P1\s+runs?\s+(?:product\s+)?(?:tests|builds|browser checks)",
            r"P1\s+(?:reruns|verifies)\s+(?:scope|locked checks|deterministic checks|local delivery)",
            r"P1['’]s independent deterministic verification",
            r"P1\s+(?:promote|promotes|deliver|delivers|deploys)",
            r"P1\s+->[^\\n]+->\s*P1\s+reruns",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, self.corpus, flags=re.IGNORECASE), pattern)

    def test_p1_scheduler_is_bounded_and_async(self):
        for marker in [
            "bounded scheduler tick",
            "watcher event queue",
            "socket-scoped P1 inbox",
            "dispatch all ready lanes without waiting",
            "ownership queue",
        ]:
            self.assertIn(marker, self.corpus)

        self.assertNotIn("timeout 600", self.references["routing.md"])
        self.assertNotIn("Use one filesystem wait for the blocking wave", self.references["routing.md"])
        self.assertIn("P1 does not call await_receipts.py", self.references["routing.md"])

    def test_delivery_graph_separates_control_and_delivery_planes(self):
        for marker in [
            "PERSISTENT P1 CONTROL PLANE",
            "P2-P9 DELIVERY PLANE",
            "INBOX",
            "SCHEDULER TICK",
            "OWNERSHIP QUEUE",
            "RUN WATCHER",
            "ASYNC SIGNAL",
            "COMPACT VERIFIER",
            "P5 INTEGRATE + DEPLOY",
        ]:
            self.assertIn(marker, self.asset_text)

        self.assertNotIn("P1 PROMOTE / DELIVER", self.asset_text)
        self.assertNotIn("P1 reruns", self.asset_text)


if __name__ == "__main__":
    unittest.main()
