import unittest
from pathlib import Path

from scripts.verify_complexity import verify


class ComplexityTest(unittest.TestCase):
    def test_replacement_has_one_state_and_identity_owner(self):
        report = verify(Path("."))
        self.assertEqual([], report["errors"])

    def test_skill_is_at_most_350_words(self):
        report = verify(Path("."))
        self.assertLessEqual(report["skill_words"], 350)


if __name__ == "__main__":
    unittest.main()
