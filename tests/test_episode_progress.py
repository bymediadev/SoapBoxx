"""Episode-to-episode progress telemetry (no persistence unless env enables it)."""

import json
import os
import tempfile
import unittest

from backend import episode_progress as ep


class TestEpisodeProgress(unittest.TestCase):
    def test_compute_progress_delta_three_lines(self) -> None:
        prev = {
            "thesis": "Markets are efficient in the long run.",
            "grounded_evidence_count": 2,
            "signal_mode": "LOW_SIGNAL",
        }
        curr = {
            "thesis": "Behavioral bias drives short-term mispricing.",
            "grounded_evidence_count": 4,
            "signal_mode": "MEDIUM_SIGNAL",
        }
        lines = ep.compute_progress_delta_lines(prev, curr)
        self.assertEqual(len(lines), 3)
        self.assertIn("Thesis direction changed", lines[0])
        self.assertIn("stronger support", lines[1])
        self.assertIn("strengthened", lines[2].lower())

    def test_compute_progress_thesis_stable_band(self) -> None:
        t = "One clear argument about climate policy with tension."
        prev = {"thesis": t, "grounded_evidence_count": 2, "signal_mode": "MEDIUM_SIGNAL"}
        curr = {"thesis": t, "grounded_evidence_count": 2, "signal_mode": "MEDIUM_SIGNAL"}
        lines = ep.compute_progress_delta_lines(prev, curr)
        self.assertIn("aligns with last episode", lines[0])
        self.assertIn("unchanged", lines[1])
        self.assertIn("unchanged", lines[2])

    def test_show_key_explicit_overrides_hash(self) -> None:
        r3: dict = {"episode_snapshot": {"title": "T", "creator": "C"}}
        sk = ep.show_key_from_meta({"show_key": "my_show"}, r3)
        self.assertEqual(sk, "my_show")

    def test_persistence_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state.json")
            old_environ = os.environ.get("SOAPBOXX_EPISODE_PROGRESS")
            old_path = os.environ.get("SOAPBOXX_EPISODE_PROGRESS_STATE")
            try:
                os.environ["SOAPBOXX_EPISODE_PROGRESS"] = "1"
                os.environ["SOAPBOXX_EPISODE_PROGRESS_STATE"] = path
                self.assertIsNone(ep.load_previous_snapshot("k1"))
                snap = {
                    "version": 1,
                    "episode_id": "e1",
                    "generated_at": "2026-01-01T00:00:00+00:00",
                    "show_key": "k1",
                    "thesis": "A",
                    "thesis_fingerprint": "th_x",
                    "core_problem": "",
                    "signal_mode": "LOW_SIGNAL",
                    "segment_count": 1,
                    "grounded_evidence_count": 2,
                    "export_structural_tier": "full",
                    "action_fingerprint": "fp_y",
                }
                ep.save_snapshot_for_show("k1", snap)
                loaded = ep.load_previous_snapshot("k1")
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertEqual(loaded.get("episode_id"), "e1")
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.assertIn("k1", data.get("shows") or {})
            finally:
                if old_environ is None:
                    os.environ.pop("SOAPBOXX_EPISODE_PROGRESS", None)
                else:
                    os.environ["SOAPBOXX_EPISODE_PROGRESS"] = old_environ
                if old_path is None:
                    os.environ.pop("SOAPBOXX_EPISODE_PROGRESS_STATE", None)
                else:
                    os.environ["SOAPBOXX_EPISODE_PROGRESS_STATE"] = old_path


if __name__ == "__main__":
    unittest.main()
