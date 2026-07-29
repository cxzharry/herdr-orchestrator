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
            "integrates after validator-clean receipts",
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
            "same-workspace P1 inbox",
            "dispatch all ready lanes without waiting",
            "ownership queue",
        ]:
            self.assertIn(marker, self.corpus)

        self.assertNotIn("timeout 600", self.references["routing.md"])
        self.assertNotIn("Use one filesystem wait for the blocking wave", self.references["routing.md"])
        self.assertIn("P1 does not call await_receipts.py", self.references["routing.md"])

    def test_dynamic_names_are_runtime_display_not_stable_identity(self):
        self.assertIn("p1_orchestrator", self.skill)
        self.assertIn("reserve/rename/verify", self.skill)
        self.assertIn("On every turn or compaction", self.skill)
        self.assertIn("next_controller_action.py", self.skill)
        self.assertIn("p{slot}_{role}_{task}", self.references["routing.md"])

    def test_delivery_graph_separates_control_and_delivery_planes(self):
        for marker in [
            "PERSISTENT P1 CONTROL PLANE",
            "P2-P9 DELIVERY PLANE",
            "ONE HERDR WORKSPACE",
            "P1 + P2-P9 SAME WORKSPACE",
            "CROSS-SPACE PROHIBITED",
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

    def test_contract_forbids_cross_workspace_pool_sharing(self):
        required_markers = [
            "P1 and every worker used by that P1 stay in the same Herdr workspace",
            "Another workspace on the same socket is a separate pool",
            "Never adopt, dispatch, auto-move, prompt, receipt, event, or session-share across workspace boundaries",
            "If a worker moves out of the workspace, mark it lost and create or bind a local replacement",
            "If a worker moves inside the same workspace, preserve the lane and session",
        ]
        for marker in required_markers:
            self.assertIn(marker, self.corpus)

        forbidden_patterns = [
            r"multiple spaces may share one Herdr socket",
            r"cross-workspace (?:recovery|verification|adoption)",
            r"P1 may move to another Herdr workspace",
            r"P1 workspace is not pool ownership",
            r"worker may live in a different workspace",
            r"two spaces (?:share|to dispatch)",
            r"separate controller scope",
            r"two controller scopes on the same Herdr socket",
            r"adopts? a unique legacy workspace ledger",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, self.corpus, flags=re.IGNORECASE), pattern)


if __name__ == "__main__":
    unittest.main()
