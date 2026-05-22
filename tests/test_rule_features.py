"""V1 rule-based features — reproducible, no LLM."""

from backend.features import extract_rule_features


TEXT = """
Host: Welcome back. Today Spirit Airlines — what happened?
Guest: They filed for bankruptcy after fares stopped covering fuel.
Host: When did you first see trouble?
Guest: Cancellations spiked in twenty twenty two anyway.
Host: Subscribe for our next episode on regional carriers.
""" * 2


def test_rule_features_reproducible():
    a = extract_rule_features(TEXT)
    b = extract_rule_features(TEXT)
    assert a == b
    assert a["feature_source"] == "rule_based"
    assert a["question_count"] >= 3
    assert a["cta_present"] is True
    assert a["topic_changes"] >= 1


def test_speaker_talk_split():
    r = extract_rule_features(TEXT)
    assert r["guest_talk_percentage"] + r["host_talk_percentage"] == 100.0
    assert r["speaking_turns"] >= 4
