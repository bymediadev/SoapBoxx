# tests/test_clip_engine_v2.py
import pytest

from backend.clip_engine_v2 import MIN_CLIP_SCORE, extract_clips_v2


def _segs2():
    return [
        {
            "id": "s1",
            "text": (
                "The cia and israel both influence us foreign policy through intelligence channels. "
                "This happens because the threat perception is shared at the white house."
            ),
            "start_time": 10.0,
            "end_time": 40.0,
        },
        {
            "id": "s2",
            "text": "Iran policy follows the same mechanism because the pentagon and congress align on perception.",
            "start_time": 50.0,
            "end_time": 80.0,
        },
    ]


def _claims3():
    return [
        {
            "id": "c1",
            "text": "The cia and israel both influence us foreign policy through intelligence channels.",
            "claim_score": 5.0,
        },
        {
            "id": "c2",
            "text": "This happens because the threat perception is shared at the white house.",
            "claim_score": 4.0,
        },
        {
            "id": "c3",
            "text": "Iran policy follows the same mechanism because the pentagon and congress align on perception.",
            "claim_score": 3.0,
        },
    ]


def test_fail_closed_empty_claims():
    r = extract_clips_v2(accepted_claims=[], evaluation_map={}, source_segments=[{"id": "x", "text": "a"}])
    assert r.get("clips") == []
    assert "NO_CLIPS" in (r.get("reason") or "")


def test_happy_produces_clips_with_evidence():
    cl = _claims3()
    em = {"c1": "s1", "c2": "s1", "c3": "s2"}
    r = extract_clips_v2(accepted_claims=cl, evaluation_map=em, source_segments=_segs2())
    assert len(r["clips"]) >= 1
    c0 = r["clips"][0]
    assert c0["claim_ids"]
    assert c0["segment_ids"]
    assert c0["start_time"] <= c0["end_time"]
    assert c0["clip_type"] in ("ASSERTION", "EXPLANATION", "NARRATIVE")
    assert c0["clip_score"] >= MIN_CLIP_SCORE
    assert c0.get("suggested_title")
    assert c0["suggested_title"].lower().startswith("the cia")


def test_thesis_optional_no_crash():
    r = extract_clips_v2(
        accepted_claims=_claims3(),
        evaluation_map={"c1": "s1", "c2": "s1", "c3": "s2"},
        source_segments=_segs2(),
        thesis="intelligence and policy overlap across regions",
    )
    assert "clips" in r


def test_rejects_unmapped_claim():
    r = extract_clips_v2(
        accepted_claims=[{"id": "c1", "text": "the cia and israel influence us policy through many channels and detail."}],
        evaluation_map={},
        source_segments=[{"id": "s1", "text": "a", "start_time": 0, "end_time": 1}],
    )
    assert r.get("clips") == [] and "NO_CLIPS" in (r.get("reason") or "")


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
