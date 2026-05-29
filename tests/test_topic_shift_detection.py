"""Topic-shift detection — narrative pivot phrases."""

from backend.features.rule_based import topic_changes


def test_discourse_pivots_counted():
    text = (
        "Host: Today on the show we visit a factory town. "
        "Years later the economy collapsed. Meanwhile workers left. "
        "But first, how did it start?"
    )
    assert topic_changes(text) >= 2


def test_anyway_still_counts():
    text = "Host: Anyway, moving on to the next beat."
    assert topic_changes(text) >= 1
