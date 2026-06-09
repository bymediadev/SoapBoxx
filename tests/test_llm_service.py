"""Gemini model selection and fallback."""

from unittest.mock import patch

from backend.llm_service import (
    _should_try_next_model,
    narrative_model_candidates,
    run_gemini_json,
)


def test_default_model_is_25_flash_not_20():
    with patch.dict("os.environ", {}, clear=True):
        assert narrative_model_candidates()[0] == "gemini-2.5-flash"


def test_custom_primary_then_fallbacks():
    env = {
        "SOAPBOXX_NARRATIVE_MODEL": "gemini-3.1-flash-lite",
        "SOAPBOXX_NARRATIVE_MODEL_FALLBACKS": "gemini-2.5-flash",
    }
    with patch.dict("os.environ", env, clear=True):
        names = narrative_model_candidates()
        assert names[0] == "gemini-3.1-flash-lite"
        assert "gemini-2.5-flash" in names
        assert "gemini-2.5-flash-lite" in names


def test_should_try_next_on_429_and_404():
    assert _should_try_next_model(429, "quota exceeded")
    assert _should_try_next_model(404, "model not found")
    assert not _should_try_next_model(400, "bad request")


@patch("backend.llm_service.gemini_api_key", return_value="test-key")
@patch("backend.llm_service._call_gemini_model")
def test_run_gemini_json_falls_back_on_quota(mock_call, _mock_key):
    mock_call.side_effect = [
        (None, 429, "quota exceeded for gemini-2.0-flash"),
        ({"ok": True, "_model_used": "gemini-2.5-flash-lite"}, 200, ""),
    ]
    result = run_gemini_json(
        system_prompt="sys",
        user_prompt="user",
        models=["gemini-2.0-flash", "gemini-2.5-flash-lite"],
    )
    assert result == {"ok": True, "_model_used": "gemini-2.5-flash-lite"}
    assert mock_call.call_count == 2
