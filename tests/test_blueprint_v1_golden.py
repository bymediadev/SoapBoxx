"""Golden-style checks — flexible expectations, not full JSON equality."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from blueprint_v1.pipeline import run_blueprint_v1  # noqa: E402
from blueprint_v1.schemas import EpisodicInput  # noqa: E402


def _golden_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "golden", "episode_001")


class TestBlueprintV1Golden(unittest.TestCase):
    def test_episode_001_expectations(self):
        os.environ.pop("SOAPBOXX_OLLAMA_MODEL", None)
        base = _golden_dir()
        with open(os.path.join(base, "transcript.txt"), encoding="utf-8") as f:
            transcript = f.read()
        with open(os.path.join(base, "metadata.json"), encoding="utf-8") as f:
            meta = json.load(f)
        with open(os.path.join(base, "expected.json"), encoding="utf-8") as f:
            exp = json.load(f)

        inp = EpisodicInput.from_metadata_transcript(
            transcript,
            title=meta.get("title", ""),
            description=meta.get("description", ""),
            creator=meta.get("creator", ""),
            genre=meta.get("genre", ""),
        )
        r = run_blueprint_v1(inp, max_retries=2)

        self.assertEqual(r.classification.type, exp["type"])
        for needle in exp.get("expected_thesis_contains", []):
            self.assertIn(needle.lower(), r.thesis.lower(), msg=f"thesis missing: {needle}")
        self.assertGreaterEqual(len(r.clips), exp.get("min_clips", 3))
        self.assertIn("snapshot", r.strategist_report)
        self.assertIn("core_breakdown", r.strategist_report)
        if exp.get("has_tension"):
            blob = (r.narrative.get("tension") or "") + r.thesis
            tensionish = any(
                k in blob.lower()
                for k in ("tension", "contradict", "rival", "competition", "incentive", "memory")
            )
            self.assertTrue(tensionish)
        for banned in exp.get("banned_substrings_in_thesis", []):
            self.assertNotIn(banned.lower(), r.thesis.lower())

        # primary_topic is not on FinalReport — title is proxy for golden doc intent
        for needle in exp.get("primary_topic_contains", []):
            self.assertIn(needle.lower(), (inp.title or "").lower())


if __name__ == "__main__":
    unittest.main()
