"""
AssemblyAI pre-recorded STT for SoapBoxx Layer 0.

Uses the official SDK when installed; falls back to REST with required
``speech_models`` per https://www.assemblyai.com/docs/llms.txt
"""

from __future__ import annotations

import io
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.services.assemblyai_format import format_diarized_utterances


def assemblyai_api_key() -> str:
    return (os.getenv("ASSEMBLYAI_API_KEY") or "").strip()


def assemblyai_base_url() -> str:
    """US default; set ASSEMBLYAI_API_BASE=https://api.eu.assemblyai.com for EU."""
    return (os.getenv("ASSEMBLYAI_API_BASE") or "https://api.assemblyai.com").rstrip("/")


def assemblyai_speech_models() -> List[str]:
    """
    Required on every pre-recorded submit — ordered fallback list.
    Override: ASSEMBLYAI_SPEECH_MODELS=universal-3-pro,universal-2
    """
    raw = (os.getenv("ASSEMBLYAI_SPEECH_MODELS") or "").strip()
    if raw:
        return [part.strip() for part in raw.split(",") if part.strip()]
    return ["universal-3-pro", "universal-2"]


def assemblyai_keyterms() -> Optional[List[str]]:
    raw = (os.getenv("SOAPBOXX_ASSEMBLYAI_KEYTERMS") or "").strip()
    if not raw:
        return None
    terms = [t.strip() for t in raw.split(",") if t.strip()]
    return terms or None


def _poll_timeout_seconds() -> int:
    try:
        from backend.stt_config import accuracy_mode_enabled

        return 3600 if accuracy_mode_enabled() else 1800
    except ImportError:
        return 1800


def _result_from_transcript_obj(
    *,
    text: str,
    utterances: Optional[List[Dict[str, Any]]],
    verbose: bool,
) -> Union[str, Dict[str, Any]]:
    if utterances:
        labeled, segments = format_diarized_utterances(utterances)
        final_text = labeled or text
    else:
        final_text = text
        segments = []

    if not final_text:
        err = "Error: AssemblyAI returned empty transcription"
        return err if not verbose else {"transcript": "", "segments": [], "error": err}

    if verbose:
        return {
            "transcript": final_text,
            "segments": segments,
            "diarized": bool(utterances),
        }
    return final_text


def _transcribe_sdk(
    audio_data: bytes,
    *,
    api_key: str,
    language: Optional[str],
    verbose: bool,
) -> Union[str, Dict[str, Any]]:
    import assemblyai as aai

    aai.settings.api_key = api_key
    base = assemblyai_base_url()
    if base != "https://api.assemblyai.com":
        aai.settings.base_url = base

    config_kwargs: Dict[str, Any] = {
        "speech_models": assemblyai_speech_models(),
        "speaker_labels": True,
    }
    if language:
        config_kwargs["language_code"] = language
    keyterms = assemblyai_keyterms()
    if keyterms:
        config_kwargs["keyterms_prompt"] = keyterms

    config = aai.TranscriptionConfig(**config_kwargs)
    transcript = aai.Transcriber(config=config).transcribe(io.BytesIO(audio_data))

    if transcript.status == aai.TranscriptStatus.error:
        err = f"Error: AssemblyAI transcription error: {transcript.error}"
        return err if not verbose else {"transcript": "", "segments": [], "error": err}

    utterances = []
    if getattr(transcript, "utterances", None):
        for u in transcript.utterances:
            utterances.append(
                {
                    "speaker": getattr(u, "speaker", None),
                    "text": getattr(u, "text", ""),
                    "start": getattr(u, "start", 0),
                    "end": getattr(u, "end", 0),
                }
            )

    return _result_from_transcript_obj(
        text=(transcript.text or "").strip(),
        utterances=utterances or None,
        verbose=verbose,
    )


def _transcribe_http(
    audio_data: bytes,
    *,
    api_key: str,
    language: Optional[str],
    verbose: bool,
) -> Union[str, Dict[str, Any]]:
    import requests

    base = assemblyai_base_url()
    headers = {"authorization": api_key}

    upload = requests.post(
        f"{base}/v2/upload",
        headers=headers,
        data=audio_data,
        timeout=120,
    )
    if upload.status_code != 200:
        err = f"AssemblyAI upload failed: {upload.text}"
        return err if not verbose else {"transcript": "", "segments": [], "error": err}

    upload_url = upload.json().get("upload_url")
    if not upload_url:
        err = "AssemblyAI upload failed: missing upload_url"
        return err if not verbose else {"transcript": "", "segments": [], "error": err}

    body: Dict[str, Any] = {
        "audio_url": upload_url,
        "speech_models": assemblyai_speech_models(),
        "speaker_labels": True,
    }
    if language:
        body["language_code"] = language
    keyterms = assemblyai_keyterms()
    if keyterms:
        body["keyterms_prompt"] = keyterms

    submit = requests.post(
        f"{base}/v2/transcript",
        headers=headers,
        json=body,
        timeout=60,
    )
    if submit.status_code != 200:
        err = f"AssemblyAI transcription failed: {submit.text}"
        return err if not verbose else {"transcript": "", "segments": [], "error": err}

    transcript_id = submit.json().get("id")
    if not transcript_id:
        err = "AssemblyAI transcription failed: missing transcript id"
        return err if not verbose else {"transcript": "", "segments": [], "error": err}

    deadline = time.time() + _poll_timeout_seconds()
    poll_url = f"{base}/v2/transcript/{transcript_id}"
    while time.time() < deadline:
        res = requests.get(poll_url, headers=headers, timeout=60).json()
        status = res.get("status")
        if status == "completed":
            return _result_from_transcript_obj(
                text=str(res.get("text") or "").strip(),
                utterances=res.get("utterances"),
                verbose=verbose,
            )
        if status == "error":
            err = f"AssemblyAI transcription error: {res.get('error')}"
            return err if not verbose else {"transcript": "", "segments": [], "error": err}
        time.sleep(3)

    err = f"Error: AssemblyAI transcription timed out after {_poll_timeout_seconds()}s"
    return err if not verbose else {"transcript": "", "segments": [], "error": err}


def transcribe_assemblyai_audio(
    audio_data: bytes,
    *,
    api_key: str,
    language: Optional[str] = "en",
    verbose: bool = False,
) -> Union[str, Dict[str, Any]]:
    """Transcribe podcast audio with diarization → Host/Guest lines for Layer 1 metrics."""
    if not api_key:
        err = "Error: No AssemblyAI API key configured — set ASSEMBLYAI_API_KEY"
        return err if not verbose else {"transcript": "", "segments": [], "error": err}

    try:
        return _transcribe_sdk(
            audio_data, api_key=api_key, language=language, verbose=verbose
        )
    except ImportError:
        return _transcribe_http(
            audio_data, api_key=api_key, language=language, verbose=verbose
        )
