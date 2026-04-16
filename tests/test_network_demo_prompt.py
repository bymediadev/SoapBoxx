"""Regression: network-facing snapshot prompt must keep specificity + anti-template rules."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from blueprint_v1.prompts import NETWORK_DEMO_EPISODE_SNAPSHOT_PROMPT  # noqa: E402


class TestNetworkDemoPrompt(unittest.TestCase):
    def test_contains_absolute_rules_and_specificity(self) -> None:
        p = NETWORK_DEMO_EPISODE_SNAPSHOT_PROMPT
        self.assertIn("# ABSOLUTE RULES", p)
        self.assertIn("Every bullet point must map to a distinct moment", p)
        self.assertIn("If two bullets could apply to multiple episodes", p)
        self.assertIn("No reusable sentence test", p)
        self.assertIn("EPISODE INTELLIGENCE SNAPSHOT", p)


if __name__ == "__main__":
    unittest.main()
