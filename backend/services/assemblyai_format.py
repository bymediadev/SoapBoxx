"""Format AssemblyAI diarized utterances for SoapBoxx Layer 1 metrics."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def format_diarized_utterances(
    utterances: List[Dict[str, Any]],
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Map AssemblyAI speaker labels to Host/Guest lines for rule_based features.

    First distinct speaker → Host; second → Guest; further → Guest N.
    """
    speaker_map: Dict[str, str] = {}
    lines: List[str] = []
    segments: List[Dict[str, Any]] = []

    for item in utterances or []:
        if not isinstance(item, dict):
            continue
        sp = str(item.get("speaker") or "A")
        if sp not in speaker_map:
            if not speaker_map:
                speaker_map[sp] = "Host"
            elif len(speaker_map) == 1:
                speaker_map[sp] = "Guest"
            else:
                speaker_map[sp] = f"Guest {len(speaker_map)}"
        label = speaker_map[sp]
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"{label}: {text}")
        try:
            start_ms = float(item.get("start") or 0)
            end_ms = float(item.get("end") or start_ms)
        except (TypeError, ValueError):
            start_ms = 0.0
            end_ms = 0.0
        segments.append(
            {
                "start_time": round(start_ms / 1000.0, 3),
                "end_time": round(end_ms / 1000.0, 3),
                "text": text,
            }
        )

    return "\n".join(lines), segments
