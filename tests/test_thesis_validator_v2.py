import pytest

from backend.thesis_validator_v2 import is_valid_thesis, thesis_validation_failure_reason


def test_rejects_keyword_list_thesis():
    t = "China; Israel; US Foreign Policy"
    assert thesis_validation_failure_reason(t) == "THESIS_KEYWORD_LIST"
    assert not is_valid_thesis(t)


def test_rejects_too_short():
    assert thesis_validation_failure_reason("Israel and CIA are bad") == "THESIS_TOO_SHORT"


def test_accepts_structured_sentence():
    t = (
        "This episode suggests that intelligence channels connect the pentagon and congress "
        "on threat perception because repeated claims across independent segments cite the same mechanism."
    )
    assert is_valid_thesis(t)


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
