# tests/test_atomic_pipeline.py
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from atomic_pipeline import (  # noqa: E402
    Claim,
    envelope_to_json,
    run_atomic_pipeline,
    verify_claims,
)


class TestAtomicPipeline(unittest.TestCase):
    def test_envelope_json_has_required_keys(self):
        r = run_atomic_pipeline("")
        d = envelope_to_json(r)
        for k in (
            "claims",
            "verification",
            "topic_graph",
            "insights",
            "clips",
            "guest_recommendations",
            "actions",
        ):
            self.assertIn(k, d)

    def test_empty_transcript_is_safe(self):
        r = run_atomic_pipeline("")
        self.assertEqual(r.claims, [])
        self.assertEqual(r.topic_graph.nodes, [])
        self.assertEqual(r.guest_recommendations, [])

    def test_guests_empty_when_topic_graph_empty(self):
        r = run_atomic_pipeline("Hi. Okay. Yeah.")
        self.assertEqual(r.guest_recommendations, [])

    def test_blocked_when_verification_mismatched(self):
        c = [
            Claim(
                id="a1",
                timestamp=0.0,
                raw_statement="Something happened in 1776 that mattered for governance.",
                category="historical_fact",
                confidence="high",
                evidence_basis="explicit_transcript",
            )
        ]
        r = run_atomic_pipeline("ignored", claims=c, verification=[])
        self.assertEqual(r.insights, [])
        self.assertEqual(r.guest_recommendations, [])
        self.assertEqual(r.clips, [])

    def test_supported_cluster_produces_graph_guests_insights(self):
        transcript = """
[10.0s] In 1877 the Nez Perce faced forced removal from their homeland by federal policy.
[12.0s] In 1877 military campaigns targeted the Nez Perce during that forced removal.
[400.0s] Leadership disagreements shaped whether groups would negotiate or move quickly.
"""
        r = run_atomic_pipeline(transcript)
        self.assertGreaterEqual(len(r.claims), 2)
        supported = sum(1 for v in r.verification if v.status == "supported")
        self.assertGreaterEqual(supported, 1)
        if len(r.topic_graph.nodes) >= 1:
            self.assertTrue(all(len(n.evidence_claim_ids) >= 2 for n in r.topic_graph.nodes))

    def test_clip_reduction_when_mostly_low_confidence(self):
        claims = [
            Claim(
                id="a1",
                timestamp=0.0,
                raw_statement="x y z x y z x y z x y z x y z x y z x y z x y z x y z x y z x y z",
                category="unclear",
                confidence="low",
                evidence_basis="explicit_transcript",
            ),
            Claim(
                id="a2",
                timestamp=1.0,
                raw_statement="a b c a b c a b c a b c a b c a b c a b c a b c a b c a b c a b c",
                category="unclear",
                confidence="low",
                evidence_basis="explicit_transcript",
            ),
        ]
        ver = verify_claims(claims)
        r = run_atomic_pipeline("", claims=claims, verification=ver)
        diag = r.diagnostics or {}
        self.assertTrue(diag.get("clip_reduction_applied"))

    def test_contrarian_guest_when_graph_nonempty(self):
        transcript = """
[1.0s] In 1776 certain colonies declared independence with articulated grievances.
[2.0s] In 1776 those grievances included taxation and representation conflicts.
[3.0s] In 1776 military escalation was not inevitable from the first protests.
"""
        r = run_atomic_pipeline(transcript)
        if r.topic_graph.nodes:
            types = {g.guest_type for g in r.guest_recommendations}
            self.assertIn("contrarian", types)


if __name__ == "__main__":
    unittest.main()
