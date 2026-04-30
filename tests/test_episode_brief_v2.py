import pytest

from backend.episode_brief_v2 import (
    MIN_SPINE_CLAIMS,
    build_episode_brief_v2,
    classify_spine_row,
    empty_episode_brief_v2,
    spine_hard_gate,
)


def test_empty_contract_shape():
    b = empty_episode_brief_v2()
    assert b["thesis"] is None
    assert b["status"]["is_shippable"] is False
    assert b["claims"] == []


def test_classify_promo_vs_interview():
    t, e = classify_spine_row(
        text="You can build a custom CRM on Odoo for your hottest prospects.",
        decision="ACCEPTED",
        reason_codes=[],
    )
    assert t == "promo" and e is False
    t2, e2 = classify_spine_row(
        text="The senate panel released a twelve page report naming three officials in March 2019.",
        decision="ACCEPTED",
        reason_codes=[],
    )
    assert t2 == "interview" and e2 is True


def test_spine_gate_cta():
    assert spine_hard_gate({"text": "Sign up now for the free trial today only."}) == "SPINE_CTA_OR_PROMO"


def test_brief_filters_promo_from_spine_pool():
    segs = [
        {"id": "s1", "text": "The cia and israel influence us foreign policy through intelligence channels.", "start_time": 1.0, "end_time": 2.0},
        {"id": "s2", "text": "Congress aligned on threat perception because the pentagon received the same cables.", "start_time": 3.0, "end_time": 4.0},
        {"id": "s3", "text": "You can build a custom CRM on Odoo for your prospects and pick the plan that fits.", "start_time": 5.0, "end_time": 6.0},
        {"id": "s4", "text": "Iran policy followed the same mechanism described in state department cables.", "start_time": 7.0, "end_time": 8.0},
    ]
    b = build_episode_brief_v2(segs, metadata={"title": "T", "genre": "Business"})
    spine = [c for c in b["claims"] if c.get("is_spine_eligible")]
    assert all("crm" not in (c.get("text") or "").lower() and "odoo" not in (c.get("text") or "").lower() for c in spine)
    assert b["metadata"]["genre"] == "Business"
    assert len(spine) >= MIN_SPINE_CLAIMS or b["status"]["fail_reasons"]


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
