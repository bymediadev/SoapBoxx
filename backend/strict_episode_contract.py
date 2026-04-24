"""
Production-style **strict JSON contract** for episode extraction (separate from v2 brief shape).

Ollama must return only ``{"data": {...}, "metadata": {...}}`` matching
:data:`STRICT_EPISODE_CONTRACT_SCHEMA`.
:class:`map_strict_contract_to_v2_brief` adapts into the legacy v2 brief dict consumed by
``episode_report_v3.build_v3_report``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

# Canonical contract (API-shaped; all keys required in validation).
STRICT_EPISODE_CONTRACT_SCHEMA: Dict[str, Any] = {
    "data": {
        "episode_snapshot": {
            "title": "string",
            "core_thesis": "string",
            "summary": "string",
        },
        "key_topics": ["string"],
        "key_moments": [{"timestamp": "string", "description": "string"}],
        "insights": ["string"],
        "actionable_takeaways": ["string"],
        "notable_quotes": ["string"],
        "guest_profile": {"name": "string", "role": "string", "expertise": ["string"]},
    },
    "metadata": {
        "model": "string",
        "warnings": ["string"],
        "error": "string",
    },
}


STRICT_CONTRACT_SYSTEM_PROMPT = """You MUST return ONLY valid JSON.

STRICT OUTPUT CONTRACT:
- Output must be a single JSON object.
- Top-level keys MUST be exactly:
  1. "data"
  2. "metadata"

RULES:
- "data" contains the full episode brief/intelligence object.
- "metadata" contains logs, warnings, model info.
- Do NOT output anything outside JSON (no markdown, no commentary, no backticks).
- If you cannot comply, return an empty valid structure:
  {
    "data": {},
    "metadata": {"error": "failed_to_generate"}
  }

This structure is REQUIRED for downstream system compatibility. Do not deviate.

Your output MUST strictly follow this schema:

""" + json.dumps(
    STRICT_EPISODE_CONTRACT_SCHEMA, indent=2, ensure_ascii=False
) + """

Rules:
- ALL fields inside "data" are REQUIRED (use "" or [] when unknown).
- "metadata" must be an object (use empty strings / empty warning lists when unknown).
- Arrays must be JSON arrays of the correct element types (never a single string).
- No null values — use "" or [].
- Do NOT invent timestamps for key_moments unless clearly present in INPUT.
- Keep strings concise but meaningful; no duplicate list entries.
- No nested objects beyond the schema.
- Content minimums for downstream compatibility:
  - episode_snapshot.title >= 6 chars
  - episode_snapshot.core_thesis >= 20 chars
  - episode_snapshot.summary >= 24 chars
  - key_topics must contain >= 1 item
  - insights must contain >= 1 item (each >= 18 chars)
  - actionable_takeaways must contain >= 1 item (each >= 12 chars)
  - key_moments/notable_quotes are optional but must be correctly typed
  - guest_profile strings should be meaningful when available

CRITICAL:
Any response not matching this schema EXACTLY will be discarded downstream.
Return ONLY valid JSON with a single top-level object: {"data": { ... }, "metadata": { ... }}.
"""


def build_strict_contract_repair_system() -> str:
    return """You are a JSON repair tool.

Your ONLY job is to convert the INPUT into valid JSON that matches this schema EXACTLY:

""" + json.dumps(
        STRICT_EPISODE_CONTRACT_SCHEMA, indent=2, ensure_ascii=False
    ) + """

Rules:
- Do NOT summarize or add new facts.
- Fix structure and types only.
- Ensure top-level keys are exactly "data" and "metadata".
- Ensure all required keys exist under "data".
- Replace null with "" or [].
- Return ONLY valid JSON: one object with top-level keys "data" and "metadata".
"""


def build_strict_contract_user_block(transcript_excerpt: str, metadata: Dict[str, str]) -> str:
    meta = dict(metadata or {})
    return (
        "INPUT:\n\n"
        f"Podcast Title: {meta.get('title') or ''}\n"
        f"Show / creator: {meta.get('creator') or ''}\n"
        f"Genre: {meta.get('genre') or ''}\n\n"
        "Transcript excerpt (may be truncated upstream):\n"
        f"{transcript_excerpt}\n\n"
        "Transcript Summary:\n(n/a — derive only from excerpt above)\n\n"
        "Key Segments:\n(n/a)\n\n"
        "Speaker Info:\n(n/a)\n"
    )


def build_strict_contract_repair_user(bad_output: str) -> str:
    return "INPUT (malformed or partial JSON to repair):\n\n" + bad_output[:120_000]


def _as_str_list(x: Any, *, max_items: int = 24) -> List[str]:
    if x is None:
        return []
    if isinstance(x, str):
        return [x] if x.strip() else []
    if isinstance(x, list):
        out: List[str] = []
        for it in x[:max_items]:
            s = str(it).strip() if not isinstance(it, dict) else ""
            if s:
                out.append(s)
        return out
    return []


def _as_moment_list(x: Any) -> List[Dict[str, str]]:
    if not isinstance(x, list):
        return []
    out: List[Dict[str, str]] = []
    for it in x[:24]:
        if not isinstance(it, dict):
            continue
        ts = str(it.get("timestamp") or "").strip()
        desc = str(it.get("description") or "").strip()
        out.append({"timestamp": ts, "description": desc})
    return out


def _as_guest_profile(x: Any) -> Dict[str, Any]:
    if not isinstance(x, dict):
        return {"name": "", "role": "", "expertise": []}
    ex = x.get("expertise")
    if not isinstance(ex, list):
        ex = _as_str_list(ex)
    else:
        ex = _as_str_list(ex)
    return {
        "name": str(x.get("name") or "").strip(),
        "role": str(x.get("role") or "").strip(),
        "expertise": ex,
    }


def enforce_strict_contract_envelope(output: Any) -> Dict[str, Any]:
    """
    Safety seatbelt for model drift:
    - non-object -> empty strict envelope with error
    - missing data/metadata -> auto-wrap once
    """
    if not isinstance(output, dict):
        return {"data": {}, "metadata": {"error": "non_json_output"}}
    if "data" not in output or "metadata" not in output:
        raw_data = output.get("data")
        if raw_data is None:
            raw_data = {k: v for k, v in output.items() if k != "metadata"}
        if not isinstance(raw_data, dict):
            raw_data = {}
        raw_meta = output.get("metadata")
        if not isinstance(raw_meta, dict):
            raw_meta = {}
        if "warning" not in raw_meta and "error" not in raw_meta:
            raw_meta["warning"] = "auto_wrapped"
        return {"data": raw_data, "metadata": raw_meta}
    data_obj = output.get("data")
    meta_obj = output.get("metadata")
    if not isinstance(data_obj, dict):
        data_obj = {}
    if not isinstance(meta_obj, dict):
        meta_obj = {"error": "metadata_not_object"}
    return {"data": data_obj, "metadata": meta_obj}


def validate_strict_episode_contract(obj: Any) -> Tuple[bool, str]:
    if not isinstance(obj, dict):
        return False, "root is not an object"
    keys = set(obj.keys())
    if keys != {"data", "metadata"}:
        return False, 'top-level keys must be exactly {"data","metadata"}'
    if "data" not in obj:
        return False, 'missing top-level "data"'
    d = obj.get("data")
    if not isinstance(d, dict):
        return False, '"data" must be an object'
    md = obj.get("metadata")
    if not isinstance(md, dict):
        return False, '"metadata" must be an object'
    if "warnings" in md and not isinstance(md.get("warnings"), list):
        return False, "metadata.warnings must be an array when present"
    if "model" in md and not isinstance(md.get("model"), str):
        return False, "metadata.model must be a string when present"
    if "error" in md and not isinstance(md.get("error"), str):
        return False, "metadata.error must be a string when present"
    required = (
        "episode_snapshot",
        "key_topics",
        "key_moments",
        "insights",
        "actionable_takeaways",
        "notable_quotes",
        "guest_profile",
    )
    for k in required:
        if k not in d:
            return False, f'missing data."{k}"'
    es = d.get("episode_snapshot")
    if not isinstance(es, dict):
        return False, "episode_snapshot must be an object"
    for sk in ("title", "core_thesis", "summary"):
        if sk not in es:
            return False, f"missing episode_snapshot.{sk}"
        if es[sk] is None:
            return False, f"episode_snapshot.{sk} must not be null"
        if not isinstance(es[sk], str):
            return False, f"episode_snapshot.{sk} must be a string"
    if len(str(es.get("title") or "").strip()) < 6:
        return False, "episode_snapshot.title too short (min 6 chars)"
    if len(str(es.get("core_thesis") or "").strip()) < 20:
        return False, "episode_snapshot.core_thesis too short (min 20 chars)"
    if len(str(es.get("summary") or "").strip()) < 24:
        return False, "episode_snapshot.summary too short (min 24 chars)"
    if not isinstance(d.get("key_topics"), list):
        return False, "key_topics must be an array"
    if len([x for x in d.get("key_topics") or [] if str(x or "").strip()]) < 1:
        return False, "key_topics must include at least 1 non-empty item"
    if not isinstance(d.get("key_moments"), list):
        return False, "key_moments must be an array"
    for fld in ("insights", "actionable_takeaways", "notable_quotes"):
        if not isinstance(d.get(fld), list):
            return False, f"{fld} must be an array"
    insights = [str(x).strip() for x in (d.get("insights") or []) if str(x or "").strip()]
    if len(insights) < 1:
        return False, "insights must include at least 1 non-empty item"
    if any(len(x) < 18 for x in insights[:5]):
        return False, "insights items must be at least 18 chars"
    actions = [str(x).strip() for x in (d.get("actionable_takeaways") or []) if str(x or "").strip()]
    if len(actions) < 1:
        return False, "actionable_takeaways must include at least 1 non-empty item"
    if any(len(x) < 12 for x in actions[:5]):
        return False, "actionable_takeaways items must be at least 12 chars"
    gp = d.get("guest_profile")
    if not isinstance(gp, dict):
        return False, "guest_profile must be an object"
    for gk in ("name", "role"):
        if gk not in gp or gp[gk] is None:
            return False, f"missing guest_profile.{gk}"
        if not isinstance(gp[gk], str):
            return False, f"guest_profile.{gk} must be a string"
    ex = gp.get("expertise")
    if ex is None or not isinstance(ex, list):
        return False, "guest_profile.expertise must be an array"
    for i, km in enumerate(d.get("key_moments") or []):
        if not isinstance(km, dict):
            return False, f"key_moments[{i}] must be an object"
        for kk in ("timestamp", "description"):
            if kk not in km or km[kk] is None:
                return False, f"key_moments[{i}].{kk} missing or null"
            if not isinstance(km[kk], str):
                return False, f"key_moments[{i}].{kk} must be a string"
    return True, ""


def map_strict_contract_to_v2_brief(contract_root: Dict[str, Any], metadata: Dict[str, str]) -> Dict[str, Any]:
    """Map validated strict contract → v2 brief dict for ``_normalize_brief`` / v3 pipeline."""
    meta = dict(metadata or {})
    d = dict(contract_root.get("data") or {})
    es = dict(d.get("episode_snapshot") or {})
    title = str(es.get("title") or meta.get("title") or "").strip() or (meta.get("title") or "Untitled episode")
    core_thesis = str(es.get("core_thesis") or "").strip()
    summary = str(es.get("summary") or "").strip()
    topics = _as_str_list(d.get("key_topics"))
    primary = "; ".join(topics[:5]) if topics else (core_thesis[:200] if core_thesis else "")
    why = (summary or core_thesis or "Structured extraction from transcript contract.").strip()[:900]

    narrative: List[str] = []
    for x in _as_str_list(d.get("insights"))[:3]:
        narrative.append(x)
    for x in _as_str_list(d.get("actionable_takeaways"))[:2]:
        narrative.append(f"Action: {x}")

    claims: List[Dict[str, Any]] = []
    n = 1
    for ins in _as_str_list(d.get("insights"))[:5]:
        if len(ins.split()) >= 5:
            claims.append(
                {
                    "id": f"c{n}",
                    "text": ins[:520],
                    "claim_type": "interpretation",
                    "confidence": "medium",
                    "why_it_matters": "From strict episode contract.",
                    "counter_angle": "",
                    "next_action": "verify",
                }
            )
            n += 1
    if not claims and core_thesis:
        claims.append(
            {
                "id": "c1",
                "text": core_thesis[:520],
                "claim_type": "interpretation",
                "confidence": "medium",
                "why_it_matters": (summary[:220] if summary else "Episode spine."),
                "counter_angle": "",
                "next_action": "verify",
            }
        )

    clips: List[str] = []
    for km in _as_moment_list(d.get("key_moments")):
        desc = km.get("description") or ""
        if not desc:
            continue
        ts = (km.get("timestamp") or "").strip()
        clips.append((f"{ts} — " if ts else "") + desc[:400])
    for q in _as_str_list(d.get("notable_quotes"))[:2]:
        clips.append(f"Quote: {q[:360]}")

    guests: List[Dict[str, Any]] = []
    gp = _as_guest_profile(d.get("guest_profile"))
    if gp.get("name"):
        cid = claims[0]["id"] if claims else "c1"
        guests.append(
            {
                "name": str(gp["name"])[:120],
                "title": str(gp.get("role") or "")[:120],
                "angle": "; ".join(str(x) for x in (gp.get("expertise") or []) if str(x).strip())[:400],
                "maps_to_claim_id": cid,
            }
        )

    snap = {
        "title": title[:300],
        "creator": str(meta.get("creator") or "").strip(),
        "genre": str(meta.get("genre") or "").strip(),
        "primary_topic": (primary or core_thesis or title)[:500],
        "why_it_matters": why,
    }

    return {
        "episode_snapshot": snap,
        "narrative": narrative[:3],
        "claims": claims[:5],
        "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
        "production_moves": {
            "segment_to_run": {"name": "Spine segment", "goal": core_thesis[:200] if core_thesis else ""},
            "host_questions": [
                "What is the strongest counterargument to your main claim?",
                "Which specific proof would validate or falsify your claim?",
                "What should the listener do differently this week?",
            ],
            "clip_candidates": clips[:6] or ([summary[:280]] if summary else []),
            "risk_note": "",
        },
        "guests": guests,
        "action_plan_7d": [
            {"day": "Day 1", "task": "Confirm thesis vs. tape."},
            {"day": "Day 2", "task": "Cut one beat that does not serve the thesis."},
            {"day": "Day 3-7", "task": "Ship one clip tied to the spine claim."},
        ],
    }
