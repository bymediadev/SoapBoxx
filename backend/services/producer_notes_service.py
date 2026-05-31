"""Producer notes — editing pressure points from transcript (rule-based, Layer 2).

Not Layer 1 metrics. Computed at report time from transcript + segments.
No quality scores, no prediction — pacing and structure signals only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from backend.features.rule_based import _SPEAKER_LINE, _words

_WPS = 2.5

_REHOOK = re.compile(
    r"\b("
    r"here'?s why|but then|the problem was|what happened next|"
    r"that'?s when|so here'?s|here'?s the thing|turns out|"
    r"the question is|which means|now,?|and then|suddenly"
    r")\b",
    re.I,
)

_ORIENTATION = re.compile(
    r"\b("
    r"so to recap|remember,?|who (?:is|are)|where (?:are|were) we|"
    r"let me explain|why does this matter|for context|"
    r"just to (?:be )?clear|to back up|quick reminder"
    r")\b",
    re.I,
)

_SCENE_CHANGE = re.compile(
    r"\b("
    r"in \d{4}|back in \d{4}|years later|meanwhile|across town|"
    r"at the (?:factory|plant|office|town|border)|"
    r"when (?:we|i|they) (?:arrived|got to|landed)|"
    r"on the (?:ground|scene|phone)|new (?:chapter|phase|owner)"
    r")\b",
    re.I,
)

# Long explanation block without an explicit question mark nearby.
_EXPLANATION_BLOCK_MIN_WORDS = 80


@dataclass
class ProducerMetricRow:
    metric: str
    value: str
    note: Optional[str] = None


@dataclass
class ProducerNotes:
    bullets: List[str] = field(default_factory=list)
    metrics: List[ProducerMetricRow] = field(default_factory=list)
    edit_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "bullets": list(self.bullets),
            "metrics": [
                {"metric": r.metric, "value": r.value, "note": r.note}
                for r in self.metrics
            ],
            "edit_flags": list(self.edit_flags),
        }


def _fmt_duration(seconds: float) -> str:
    s = max(0.0, float(seconds or 0))
    if s < 60:
        return f"{s:.0f}s"
    minutes = int(s // 60)
    rem = int(round(s % 60))
    if rem:
        return f"{minutes}m {rem}s"
    return f"{minutes}m"


def _segment_blocks(
    segments: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge consecutive segments into uninterrupted blocks (same stretch of speech)."""
    if not segments:
        return []
    blocks: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for seg in segments:
        try:
            start = float(seg.get("start") or 0)
            end = float(seg.get("end") or start)
        except (TypeError, ValueError):
            continue
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        speaker = None
        m = _SPEAKER_LINE.match(text)
        if m:
            speaker = m.group(1).lower()
            text = _SPEAKER_LINE.sub("", text).strip()
        if current is None:
            current = {"start": start, "end": end, "text": text, "speaker": speaker}
            continue
        gap = start - float(current["end"])
        same_speaker = speaker is None or speaker == current.get("speaker")
        if gap <= 2.0 and same_speaker:
            current["end"] = end
            current["text"] = f"{current['text']} {text}".strip()
        else:
            blocks.append(current)
            current = {"start": start, "end": end, "text": text, "speaker": speaker}
    if current:
        blocks.append(current)
    return blocks


def _blocks_from_text(text: str) -> List[Dict[str, Any]]:
    """Fallback when STT segments are missing — paragraph-based blocks."""
    blocks: List[Dict[str, Any]] = []
    t = 0.0
    for para in re.split(r"\n\s*\n", (text or "").strip()):
        p = para.strip()
        if len(p.split()) < 8:
            continue
        w = _words(p)
        dur = w / _WPS
        blocks.append({"start": t, "end": t + dur, "text": p, "speaker": None})
        t += dur
    return blocks


def _longest_and_avg_block(
    blocks: Sequence[Dict[str, Any]],
) -> tuple[float, float]:
    if not blocks:
        return 0.0, 0.0
    durs = [max(0.0, float(b["end"]) - float(b["start"])) for b in blocks]
    return max(durs), sum(durs) / len(durs)


def _rehook_positions(text: str, segments: Optional[Sequence[Dict[str, Any]]]) -> List[float]:
    """Timestamps (seconds) of re-hook phrases when segments exist."""
    positions: List[float] = []
    if segments:
        for seg in segments:
            t = str(seg.get("text") or "")
            if _REHOOK.search(t):
                try:
                    positions.append(float(seg.get("start") or 0))
                except (TypeError, ValueError):
                    positions.append(0.0)
        return positions
    t = 0.0
    for ln in (text or "").splitlines():
        s = _SPEAKER_LINE.sub("", ln.strip()).strip()
        if _REHOOK.search(s):
            positions.append(t)
        t += _words(ln) / _WPS
    return positions


def _avg_interval(positions: Sequence[float], total_runtime: float) -> Optional[float]:
    if len(positions) < 2:
        return None
    gaps = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
    gaps = [g for g in gaps if g > 0]
    if not gaps:
        return None
    return sum(gaps) / len(gaps)


def _explanation_heavy_ratio(blocks: Sequence[Dict[str, Any]]) -> tuple[float, float]:
    """Proxy: long blocks without ? vs all long blocks (not semantic fact density)."""
    if not blocks:
        return 0.0, 0.0
    expl_words = 0
    disc_words = 0
    for b in blocks:
        text = str(b.get("text") or "")
        w = _words(text)
        if w < _EXPLANATION_BLOCK_MIN_WORDS:
            continue
        if "?" in text:
            disc_words += w
        else:
            expl_words += w
    total = expl_words + disc_words
    if total == 0:
        return 0.0, 0.0
    expl_pct = round(100.0 * expl_words / total, 0)
    disc_pct = round(100.0 * disc_words / total, 0)
    return expl_pct, disc_pct


def _repeated_phrase_flags(text: str, min_words: int = 5) -> List[str]:
    """Detect near-verbatim repeated phrases (structural repetition signal)."""
    flags: List[str] = []
    sents = [s.strip().lower() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
    seen: dict[str, int] = {}
    for s in sents:
        if _words(s) < min_words:
            continue
        key = re.sub(r"\s+", " ", s)[:120]
        seen[key] = seen.get(key, 0) + 1
    repeats = [k for k, n in seen.items() if n >= 3]
    if repeats:
        sample = repeats[0][:60] + ("…" if len(repeats[0]) > 60 else "")
        flags.append(
            f"Potential repetition: similar phrasing appears multiple times "
            f'(e.g. "{sample}")'
        )
    return flags[:2]


def build_producer_notes(
    transcript: str,
    segments: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    intro_seconds: Optional[float] = None,
    topic_shift_count: Optional[int] = None,
) -> ProducerNotes:
    text = (transcript or "").strip()
    if len(text) < 40:
        return ProducerNotes(
            bullets=["Transcript too short for producer notes — run transcription first."]
        )

    seg_list = list(segments or [])
    blocks = _segment_blocks(seg_list) if seg_list else _blocks_from_text(text)
    longest, avg_len = _longest_and_avg_block(blocks)
    total_runtime = float(blocks[-1]["end"]) if blocks else _words(text) / _WPS

    rehook_pos = _rehook_positions(text, seg_list or None)
    rehook_count = len(rehook_pos)
    rehook_interval = _avg_interval(rehook_pos, total_runtime)

    scene_changes = len(_SCENE_CHANGE.findall(text))
    speaker_turns = sum(
        1 for ln in text.splitlines() if _SPEAKER_LINE.match(ln.strip())
    )
    scene_total = scene_changes + max(0, speaker_turns - 1)

    orientation = len(_ORIENTATION.findall(text))
    expl_pct, disc_pct = _explanation_heavy_ratio(blocks)

    # Development spacing proxy: avg gap between re-hooks or scene markers
    dev_markers = sorted(rehook_pos + [0.0])
    if seg_list:
        for seg in seg_list:
            if _SCENE_CHANGE.search(str(seg.get("text") or "")):
                try:
                    dev_markers.append(float(seg.get("start") or 0))
                except (TypeError, ValueError):
                    pass
    dev_markers = sorted(set(dev_markers))
    dev_interval = _avg_interval(dev_markers, total_runtime)

    metrics: List[ProducerMetricRow] = [
        ProducerMetricRow("Longest uninterrupted segment", _fmt_duration(longest)),
        ProducerMetricRow("Avg segment length", _fmt_duration(avg_len)),
        ProducerMetricRow("Re-hooks", str(rehook_count)),
    ]
    if rehook_interval is not None:
        metrics.append(
            ProducerMetricRow(
                "Avg time between re-hooks",
                _fmt_duration(rehook_interval),
            )
        )
    if dev_interval is not None and dev_interval != rehook_interval:
        metrics.append(
            ProducerMetricRow(
                "Avg time between narrative beats",
                _fmt_duration(dev_interval),
                note="Re-hooks and scene markers combined (text-detected)",
            )
        )
    metrics.extend(
        [
            ProducerMetricRow("Scene changes", str(scene_total)),
            ProducerMetricRow("Orientation resets", str(orientation)),
        ]
    )
    if expl_pct + disc_pct > 0:
        metrics.append(
            ProducerMetricRow(
                "Explanation-heavy blocks",
                f"{int(expl_pct)}%",
                note="Long blocks without explicit questions (proxy, not fact density)",
            )
        )
        metrics.append(
            ProducerMetricRow(
                "Discovery-heavy blocks",
                f"{int(disc_pct)}%",
                note="Long blocks with explicit questions (proxy)",
            )
        )

    edit_flags: List[str] = []
    if longest >= 240:
        idx = max(range(len(blocks)), key=lambda i: blocks[i]["end"] - blocks[i]["start"])
        at = _fmt_duration(blocks[idx]["start"])
        edit_flags.append(
            f"Potential drag: {_fmt_duration(longest)} uninterrupted segment at ~{at}"
        )
    elif longest >= 180:
        edit_flags.append(
            f"Potential drag: {_fmt_duration(longest)} uninterrupted segment — "
            "worth checking pacing on replay"
        )

    if dev_interval is not None and dev_interval >= 240:
        edit_flags.append(
            f"Potential slow beat spacing: narrative developments ~{_fmt_duration(dev_interval)} "
            "apart on average (text-detected)"
        )

    edit_flags.extend(_repeated_phrase_flags(text))

    abrupt = 0
    if len(blocks) >= 2:
        durs = [float(b["end"]) - float(b["start"]) for b in blocks]
        for i in range(1, len(durs)):
            if durs[i - 1] > 60 and durs[i] > 60 and abs(durs[i] - durs[i - 1]) > 120:
                abrupt += 1
    if abrupt:
        edit_flags.append(
            f"Potential weak transition: {abrupt} abrupt length shift(s) between segments"
        )

    bullets: List[str] = []
    if intro_seconds is not None and intro_seconds < 60:
        bullets.append(f"Fast entry into premise ({_fmt_duration(intro_seconds)})")
    if topic_shift_count is not None and topic_shift_count <= 1:
        bullets.append("One dominant story thread in detected text")
    if longest > 0:
        bullets.append(f"Longest uninterrupted segment: {_fmt_duration(longest)}")
    if rehook_count > 0 and rehook_interval is not None:
        bullets.append(
            f"Re-hooks about every {_fmt_duration(rehook_interval)} on average ({rehook_count} detected)"
        )
    elif rehook_count > 0:
        bullets.append(f"{rehook_count} re-hook phrase(s) detected in transcript")
    if orientation >= 3:
        bullets.append(
            f"Listener orientation resets: {orientation} (who/where/why re-grounding in text)"
        )
    if edit_flags:
        bullets.append(f"{len(edit_flags)} edit flag(s) — see below")
    elif longest < 180 and rehook_count >= 3:
        bullets.append("Pacing reads active in text — frequent re-hooks, no long drag flags")

    return ProducerNotes(
        bullets=bullets[:8],
        metrics=metrics,
        edit_flags=edit_flags[:6],
    )
