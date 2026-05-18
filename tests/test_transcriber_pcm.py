"""PCM → WAV and validation helpers for local Whisper."""

from __future__ import annotations

from backend.transcriber import (
    Transcriber,
    _is_raw_pcm_s16le,
    _pcm_s16le_to_wav_bytes,
)


def test_is_raw_pcm_s16le_detects_live_mic_bytes():
    pcm = (b"\x01\x00" * 4000)
    assert _is_raw_pcm_s16le(pcm)
    assert not _is_raw_pcm_s16le(b"RIFF" + pcm)


def test_pcm_s16le_to_wav_has_header():
    pcm = (b"\x00\x00" * 8000)
    wav = _pcm_s16le_to_wav_bytes(pcm)
    assert wav.startswith(b"RIFF")
    assert len(wav) > len(pcm)


def test_transcribe_local_rejects_tiny_buffer():
    t = Transcriber(service="local")
    # Valid PCM shape but under SOAPBOXX_MIN_WHISPER_SAMPLES
    out = t.transcribe(b"\x01\x00" * 200)
    assert out.startswith("Error:")
    assert "too short" in out.lower() or "whisper" in out.lower()
