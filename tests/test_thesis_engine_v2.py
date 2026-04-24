# tests/test_thesis_engine_v2.py
import pytest

from backend.thesis_engine_v2 import (
    MIN_CLAIMS_IN_CLUSTER,
    construct_thesis_v2,
)

SEG_A = "s1"
SEG_B = "s2"
_SEGS = [{"id": SEG_A, "t": 0.0}, {"id": SEG_B, "t": 60.0}]


def _make_claims(n: int, text_prefix: str, seg_pattern: str) -> tuple[list[dict], dict, list[dict]]:
    """Seg pattern alternates a,b for evaluation_map (seg_pattern like 'aaba')."""
    claims = []
    em = {}
    for i in range(n):
        claims.append(
            {
                "id": f"c{i+1}",
                "text": f"{text_prefix} {i} israel cia us foreign policy threat perception intelligence channels.",
            }
        )
        s = seg_pattern[i] if i < len(seg_pattern) else ("a" if i % 2 == 0 else "b")
        em[claims[-1]["id"]] = SEG_A if s == "a" else SEG_B
    return claims, em, _SEGS


def test_fail_closed_empty_claims():
    r = construct_thesis_v2(
        accepted_claims=[],
        evaluation_map={},
        source_segments=[{"id": "x"}],
    )
    assert r["thesis"] is None
    assert "NO_THESIS" in (r.get("reason") or "")


def test_fail_closed_missing_eval_map_key():
    claims, _em, segs = _make_claims(3, "x", "aab")
    r = construct_thesis_v2(
        accepted_claims=claims,
        evaluation_map={"c1": SEG_A, "c2": SEG_B},  # c3 missing
        source_segments=segs,
    )
    assert r["thesis"] is None
    assert "missing" in (r.get("reason") or "").lower() or "c3" in (r.get("reason") or "")


def test_happy_path_cluster_and_shippable_band():
    claims, em, segs = _make_claims(3, "Repeated analysis shows", "aab")
    r = construct_thesis_v2(
        accepted_claims=claims,
        evaluation_map=em,
        source_segments=segs,
    )
    assert r["thesis"] is not None
    assert len(r["supporting_clusters"]) == 1
    assert len(r["supporting_clusters"][0]["claim_ids"]) >= MIN_CLAIMS_IN_CLUSTER
    assert "structural" in r["supporting_clusters"][0]["cluster_name"] or "structural" in "ok"
    assert r["generation_status"] in ("SHIPPABLE", "UNSHIPPABLE", "INSUFFICIENT_SIGNAL")
    assert 0.0 <= r["confidence_score"] <= 1.0


def test_banned_thesis_phrase_detection():
    from backend.thesis_engine_v2 import _thesis_banned_narrative, _VAGUE_ABSTRACTIONS

    assert _thesis_banned_narrative("in this episode we talk about cia and israel israel cia us")
    assert _VAGUE_ABSTRACTIONS.search("the world order is unclear")


def test_title_leakage_rejected():
    claims, em, segs = _make_claims(3, "Repeated analysis shows", "aab")
    first = construct_thesis_v2(accepted_claims=claims, evaluation_map=em, source_segments=segs)
    assert first.get("thesis")
    r = construct_thesis_v2(
        accepted_claims=claims,
        evaluation_map=em,
        source_segments=segs,
        episode_metadata={"title": first["thesis"]},
    )
    assert r["thesis"] is None
    assert "TITLE" in (r.get("reason") or "")


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
