"""Unit tests for backend/causal_claim."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import causal_claim as cc  # noqa: E402


class TestCausalClaim(unittest.TestCase):
    def test_markers(self):
        self.assertTrue(cc.is_causal_claim("Tariffs reduce import volumes because buyers shift sourcing."))
        self.assertTrue(cc.is_causal_claim("The policy drives consolidation in regional banks."))
        self.assertFalse(cc.is_causal_claim("Trade policy remains important for investors this quarter."))

    def test_falsifiability_bypass(self):
        self.assertTrue(
            cc.is_causal_claim(
                "He was monitored during prior meetings.",
                falsifiability=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
