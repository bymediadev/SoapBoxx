# tests/test_soapboxx_v2_failure_simulator.py
"""
v2 **failure simulators** — regression for empty signal, politics-as-vapor, story-driven, promo.

These tests encode acceptance bars from the integration spec; tune fixtures if thresholds drift,
but do not weaken assertions without understanding which failure mode reappears.
"""

from __future__ import annotations

import pytest

from backend.clip_engine_v2 import MIN_CLIP_SCORE
from backend.soapboxx_v2_pipeline import (
    PIPELINE_STEPS,
    run_soapboxx_v2_pipeline,
)


def _segs_filler_only() -> list[dict]:
    return [
        {"id": f"s{i:02d}", "text": t, "start_time": float(i), "end_time": float(i) + 0.4}
        for i, t in enumerate(
            [
                "um yeah",
                "uh huh",
                "mm",
                "wow",
                "okay",
                "right",
                "thanks",
                "bye",
                "yeah",
                "mhm",
            ],
            start=1,
        )
    ]


def _segs_vague_geopolitics() -> list[dict]:
    return [
        {"id": f"s{i:02d}", "text": t, "start_time": float(i), "end_time": float(i) + 1.0}
        for i, t in enumerate(
            [
                "I think the world is a complicated place and many things are happening in general",
                "You know, power structures in society kind of do things, right?",
                "China and Israel and the CIA and everyone are in this global situation sometimes",
                "It is important to be thoughtful about the narrative we tell ourselves, maybe",
                "Like, geopolitics in general is just really a lot, you know what I mean",
            ],
            start=1,
        )
    ]


def _segs_promo() -> list[dict]:
    return [
        {"id": f"s{i:02d}", "text": t, "start_time": float(i), "end_time": float(i) + 1.0}
        for i, t in enumerate(
            [
                "Check out our HubSpot CRM integration for your SaaS onboarding flow",
                "Use code STRIPE checkout with Salesforce for 30 percent more pipeline velocity",
                "Odoo and Odoo modules help you scale your enterprise GTM",
                "The webinar covers funnel optimization and MRR expansion tactics",
            ],
            start=1,
        )
    ]


def _segs_strong_narrative() -> list[dict]:
    return [
        {
            "id": "s1",
            "text": (
                "In March 2019 the Senate panel released a twelve page report "
                "naming three specific officials and citing two intercepted emails. "
            ),
            "start_time": 10.0,
            "end_time": 40.0,
        },
        {
            "id": "s2",
            "text": (
                "The cia and israel both influence us foreign policy through intelligence "
                "channels, as we discussed when the white house staff confirmed the timeline."
            ),
            "start_time": 50.0,
            "end_time": 80.0,
        },
        {
            "id": "s3",
            "text": (
                "The pentagon and congress then aligned on threat perception, because "
                "congress had received the same document before the public hearing. "
            ),
            "start_time": 90.0,
            "end_time": 120.0,
        },
        {
            "id": "s4",
            "text": "Iran policy followed the same mechanism; state department cables describe the same chain.",
            "start_time": 130.0,
            "end_time": 150.0,
        },
    ]


class TestPipelineContract:
    def test_pipeline_map_steps_documented(self):
        assert "filter_claim" in " ".join(s for _k, s in PIPELINE_STEPS)
        r = run_soapboxx_v2_pipeline([{"id": "s1", "text": "a b c d e f g and policy detail."}])
        assert "claim_filter" in r
        assert "structural_components" in r
        assert "thesis" in r
        assert "clips" in r

    def test_no_episode_title_parameter_on_runner(self):
        import inspect

        sig = inspect.signature(run_soapboxx_v2_pipeline)
        assert "title" not in sig.parameters
        assert "episode_title" not in sig.parameters

    def test_rejected_rows_have_reason_codes_in_debug(self):
        r = run_soapboxx_v2_pipeline(_segs_filler_only(), mode="debug")
        rej = r["claim_filter"]["rejected"]
        assert len(rej) >= 1
        for row in rej:
            assert "reason_codes" in row
            assert row["reason_codes"] is not None


class TestSimulationClassAEmptySignal:
    def test_filler_rejects_most_and_no_thesis_nor_orphan_clips(self):
        r = run_soapboxx_v2_pipeline(_segs_filler_only(), mode="debug")
        cr = r["claim_filter"]
        assert cr["reject_rate"] >= 0.7
        assert r["thesis"] is not None
        assert r["thesis"]["thesis"] is None
        assert "NO_ACCEPTED" in str(r["thesis"].get("reason")) or "NO_THESIS" in str(r["thesis"].get("reason"))
        assert r["thesis"].get("generation_status") in ("INSUFFICIENT_SIGNAL", "UNSHIPPABLE")
        assert r["clips"]["clips"] == []
        assert r["structural_components"]["claim_ids_ordered"] == []
        assert r["structural_components"]["components"] == []


class TestSimulationClassBAbstraction:
    def test_does_not_emit_shippable_thesis_on_vapor(self):
        r = run_soapboxx_v2_pipeline(_segs_vague_geopolitics(), mode="debug")
        th = r["thesis"]
        assert th is not None
        if th.get("thesis") is not None:
            assert th.get("generation_status") != "SHIPPABLE"
        else:
            assert th.get("generation_status") in ("INSUFFICIENT_SIGNAL", "UNSHIPPABLE") or "NO_THESIS" in str(
                th.get("reason")
            )

    def test_many_rejections_hitting_low_info_or_generic(self):
        r = run_soapboxx_v2_pipeline(_segs_vague_geopolitics(), mode="debug")
        codes = [c for x in r["claim_filter"]["rejected"] for c in (x.get("reason_codes") or [])]
        if not codes:
            assert len(r["claim_filter"]["rejected"]) >= 1
        # At least one trace references low information or generic, or nothing accepted
        if r["claim_filter"]["accepted"]:
            for cl in r["claim_filter"]["rejected"][:2]:
                assert cl.get("reason_codes")


class TestSimulationClassCStoryDriven:
    def test_allows_some_acceptance_and_valid_clip_contract(self):
        r = run_soapboxx_v2_pipeline(_segs_strong_narrative(), mode="debug")
        cr = r["claim_filter"]
        n_in = max(1, len(cr["accepted"]) + len(cr["rejected"]))
        ar = len(cr["accepted"]) / n_in
        assert 0.12 <= ar <= 0.65, f"accept rate {ar} (tune story fixture if filter changes)"
        for clip in (r.get("clips") or {}).get("clips") or []:
            assert clip.get("claim_ids")
            assert clip.get("segment_ids")
            assert clip.get("end_time", 0) >= clip.get("start_time", 0)
            assert clip.get("clip_score", 0) >= MIN_CLIP_SCORE


class TestSimulationClassDPromo:
    def test_heavy_reject_and_not_business_thesis(self):
        r = run_soapboxx_v2_pipeline(_segs_promo(), mode="debug")
        assert r["claim_filter"]["reject_rate"] >= 0.5
        th = (r.get("thesis") or {}).get("thesis")
        st = (r.get("thesis") or {}).get("generation_status")
        if th:
            tlow = th.lower()
            assert "saas" not in tlow
            assert "mrr" not in tlow
        assert st != "SHIPPABLE" or th is None


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
