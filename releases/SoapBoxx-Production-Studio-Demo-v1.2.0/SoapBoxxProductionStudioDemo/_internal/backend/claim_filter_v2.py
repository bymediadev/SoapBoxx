# backend/claim_filter_v2.py
"""
SOAPBOXX v2 — claim entry gate (drop-in spec).

**Default assumption:** speech is *noise* until it passes *all* required checks, including
a calibrated **claim_score** (specificity, falsifiability, information density, minus
filler and abstraction) — reject when ``claim_score < CLAIM_SCORE_MIN`` (default 3),
unless rules already rejected the line (social scaffolding, generic universals, promo, …).

**Outputs:** ``filter_claim_candidates(..., mode="debug"|"production")`` returns decision traces:
``decision`` (``ACCEPTED`` / ``REJECTED``), ``stage`` (``CLAIM_FILTER``), ``reason_codes`` (stable
UPPER_SNAKE audit vocabulary), ``explanation``, ``score_breakdown`` (public names:
``filler_penalty``, ``abstraction_penalty``, ``total``). In **production**, rows are slim; set
``return_internal_debug_trace=True`` to attach ``_claim_filter_debug_full`` for internal logging.
This module does *not* verify truth; it throttles “intelligence inflation.”
"""

from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union, Literal

# --- Stable rejection / pass reason tokens (extend; do not rename casually) ---

# Gate-level (VALID_CLAIM composite)
R_SEMANTIC_INCOMPLETE = "semantic_incomplete"
R_NO_INFORMATION_WEIGHT = "no_information_weight"
R_STRUCTURAL_SPEECH = "structural_speech"
R_FILLER = "filler"
R_MULTI_TOPIC_DRIFT = "multi_topic_drift"
R_REMOVAL_REDUNDANT = "removal_redundant"

# Hard list (takes precedence when matched)
R_HARD_PODCAST_SCAFFOLD = "hard_podcast_scaffold"
R_HARD_META_COMMENTARY = "hard_meta_commentary"
R_HARD_PROMO_BUSINESS = "hard_promo_business"
R_HARD_EMOTIONAL_FILLER = "hard_emotional_filler"
R_STRUCTURAL_SOCIAL = "structural_social"
R_GENERIC_NON_CLAIM = "generic_non_claim"
R_CLAIM_SCORE = "low_claim_score"

# Causal / mechanism wording (Layer 1 — optional gate)
R_NOT_CAUSAL = "not_causal_statement"

# Success
P_PASSED = "passed_all_filters"

# Calibrated v2: claim_score = spec+fals+den - fill - abstr; reject if < this.
CLAIM_SCORE_MIN = 3
# Max per dimension in user rubric
_SCORE_MAX_DIM = 2

# Every row is traceable to this stage (for multi-stage logs later)
STAGE_CLAIM_FILTER = "CLAIM_FILTER"

# --- Public / audit reason codes (UPPER_SNAKE) — cross-stage vocabulary ---
_CODE_FILLER = "FILLER_LANGUAGE"
_CODE_PODCAST_SCAFFOLD = "PODCAST_SCAFFOLDING"  # spec spelling (scaffolding)
_CODE_TRANSITION = "TRANSITION_PHRASE"
_CODE_LOW_INFO = "LOW_INFORMATION_WEIGHT"
_CODE_GENERIC = "GENERIC_STATEMENT"
_CODE_NON_FALSIFIABLE = "NON_FALSIFIABLE"
_CODE_HIGH_ABSTRACTION = "HIGH_ABSTRACTION"
_CODE_NO_CONCRETE = "NO_CONCRETE_REFERENT"
_CODE_MULTI_TOPIC = "MULTI_TOPIC_SENTENCE"
_CODE_CONTEXT_NOISE = "CONTEXTUAL_NOISE"
_CODE_SCORE_BELOW = "SCORE_BELOW_MINIMUM"  # calibration gate
_CODE_NON_CAUSAL = "NON_CAUSAL_STATEMENT"
_CODE_HIGH_INFO = "HIGH_INFORMATION_WEIGHT"
_CODE_SPECIFIC_ATOMIC = "SPECIFIC_AND_ATOMIC"
_CODE_CLEAR_ASSERTION = "CLEAR_ASSERTION"
_CODE_TRACEABLE = "TRACEABLE_TO_EVENT"

_Segment = Union[Mapping[str, Any], Tuple[str, str]]

# Minimum words for a *candidate* to be a full-sentence idea (not a fragment)
_MIN_WORDS_SEMANTIC = 5
# Shorter lines allowed only if they carry a strong information-weight pattern
_MIN_WORDS_SHORT_OK = 3

# Words that are *only* backchannel if the whole utterance is tiny
_BACKCHANNEL_ONLY = frozenset(
    x
    for x in (
        "yeah yep yup nope uh huh um mhm mm mmhmm right okay ok sure exactly "
        "wow oh ah ha thanks thankyou thank-you thanks".split()
    )
)

_VERB_LIKE = re.compile(
    r"\b("
    r"is|are|was|were|be|been|being|have|has|had|do|does|did|will|would|should|could|may|might|must|"
    r"believe|thinks?|argue|claim|suggest|show|mean|seems?|happen|happened|occurs?|"
    r"causes?|leads?|drives?|proves?|indicates?|demonstrates?|explains?|"
    r"shifts?|affects?|affecting|increases?|decreases?|changes?|creates?|limits?|imposes?|"
    r"because|therefore|although|however|if|unless"
    r")\b",
    re.IGNORECASE,
)

# Information weight: assertion, belief, explanation, interpretation, reference
_INFO_WEIGHT = re.compile(
    r"\b("
    r"i\s+think|i\s+believe|we\s+think|i\s+mean|it\s+means|this\s+means|"
    r"because|therefore|as\s+a\s+result|the\s+reason|which\s+explains|"
    r"study|studies|data|evidence|report|research|according\s+to|fact|factual|"
    r"in\s+my\s+view|interpret|interpretation|implies?|suggests?|demonstrat"
    r")\b",
    re.IGNORECASE,
)
_NUMERAL = re.compile(r"\b(19|20)\d{2}\b|\b\d+(\.\d+)?%|\b\d{1,3}(,\d{3})+\b|\b\d+\b")

# Structural / host / bridge (broad; tune with real data)
_STRUCTURAL = re.compile(
    r"(?i)\b("
    r"welcome\s+to|thanks?\s+for\s+having|good\s+to\s+be\s+here|glad\s+to\s+be|"
    r"today'?s?\s+guest|our\s+guest\s+is|sitting\s+down\s+with|joining\s+us|"
    r"we'?re\s+talking\s+about|today\s+we|on\s+this\s+episode|in\s+this\s+episode|"
    r"so\s+with\s+that\s+said|without\s+further\s+ado|let'?s\s+(dive|get)\s+into|"
    r"before\s+we\s+go|after\s+the\s+break|we'?ll\s+be\s+right\s+back|"
    r"sponsored\s+by|brought\s+to\s+you\s+by|use\s+code|promo\s+code|"
    r"sign\s+up\s+at|download\s+the\s+app|book\s+a\s+demo|try\s+for\s+free|"
    r"onboarding|workflow|saas|crm\s+system"
    r")\b",
)

# Hard reject — podcast scaffolding
_HARD_PODCAST = re.compile(
    r"(?i)^\s*("
    r"welcome\s+to\s+the\s+show|excited\s+to\s+have|today'?s?\s+guest\s+is"
    r")",
)

# Hard reject — meta commentary about the conversation
_HARD_META = re.compile(
    r"(?i)\b("
    r"this\s+is\s+interesting\s+because|what\s+i\s+want\s+to\s+talk\s+about\s+is|"
    r"the\s+point\s+of\s+this\s+conversation|before\s+we\s+get\s+into\s+the\s+meat"
    r")\b",
)

# Hard reject — business / tool / promo (incl. product build / manage-client talk)
_HARD_PROMO = re.compile(
    r"(?i)\b("
    r"\bCRM\b|salesforce|hubspot|stripe\s+checkout|odoo|"
    r"o\.?d\.?o|"
    r"onboarding\s+flow|free\s+trial|sign\s+up\s+for|"
    r"build\s+a\s+custom\s+crm|manage\s+clients"
    r")",
)

# Social / interview scaffolding (praise, excitement — not epistemic content)
_RE_STRUCTURAL_SOCIAL = re.compile(
    r"(?i)\b("
    r"excited\s+to\s+(?:interview|have\s+you|speak|talk|chat)|"
    r"get\s+excited\s+to|top\s+of\s+the\s+list|"
    r"people\s+that\s+i\s+get\s+excited|lot\s+of\s+people.*excited|"
    r"honored\s+to\s+have|thrilled\s+to\s+be|"
    r"one\s+of\s+my\s+favorite\s+guests|mean\s+so\s+much"
    r")\b",
)

# Universals / audience pandering — no new, testable information
_RE_GENERIC_UNIVERSAL = re.compile(
    r"(?i)folks,?\s+if\s+you\W*are\W+a\s+small\s+business|"
    r"if\s+you\W*are\W+a\s+small\s+business\s+owner,?\W*you\s+understand|"
    r"you\s+understand\s+the\s+challenges\s+that\s+come|"
    r"challenges?\s+that\s+come\s+with\s+that\s+job|"
    r"as\s+we\s+all\s+know|it\s+goes\s+without\s+saying|"
    r"everyone\s+knows\s+that|we\s+all\s+agree"
)

# Hard reject — empty praise / emotional filler
_HARD_EMOTE = re.compile(
    r"(?i)^\s*("
    r"it\s+was\s+amazing|great\s+conversation|really\s+interesting\s+stuff|"
    r"so\s+insightful|loved\s+this\s+episode|such\s+great\s+energy"
    r")\s*\.?\s*$",
)

_FILLER_TICS = re.compile(
    r"(?i)^\s*("
    r"you\s+know,?\s+like|i\s+mean,?\s+you|sort\s+of|kind\s+of|um+,?\s+|uh+,?\s*"
    r")\s*$|^(yeah|yep|right|exactly|mhm|uh\shuh)\s*$"
)

# Filler / hype language (penalize in claim_score)
_RE_FILLER_WORDS = re.compile(
    r"(?i)\b("
    r"a\s+lot\s+of|very\s+excited|so\s+excited|really\s+great|amazing|incredible|folks,|"
    r"you\s+know,|i\s+mean,|just\s+want\s+to\s+say|honestly,|obviously,|"
    r"at\s+the\s+end\s+of\s+the\s+day|needless\s+to\s+say|sort\s+of|kind\s+of"
    r")\b"
)
# Abstraction: nation personification, superlatives, geopolitical hand-waving
_RE_ABSTRACTION = re.compile(
    r"(?i)\b("
    r"alone\s+in\s+the\s+world|greatest\s+(?:threat|danger|risk|challenge|enemy)|"
    r"^\s*.{0,80}\bbelieves?\s+it\s+is\s+alone|national\s+security\b.*\b(threat|greatest)\b|"
    r"is\s+the\s+greatest|is\s+the\s+biggest|everyone\s+knows|the\s+world\s+is"
    r")\b"
)


def _claim_require_causal() -> bool:
    v = (os.environ.get("SOAPBOXX_CLAIM_REQUIRE_CAUSAL") or "1").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return True


def _norm_text(s: str) -> str:
    t = unicodedata.normalize("NFKC", s or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _word_count(s: str) -> int:
    if not s:
        return 0
    return len(s.split())


def _is_backchannel_only(s: str) -> bool:
    t = s.lower().strip(".,!?-–—'\"")
    toks = t.split()
    if not toks:
        return True
    if len(toks) <= 3 and all(x in _BACKCHANNEL_ONLY for x in toks):
        return True
    return False


def _semantic_complete(s: str) -> bool:
    wc = _word_count(s)
    if wc < _MIN_WORDS_SHORT_OK:
        return False
    if wc < _MIN_WORDS_SEMANTIC and not _INFO_WEIGHT.search(s) and not _VERB_LIKE.search(s):
        return False
    if wc < _MIN_WORDS_SEMANTIC and not (_INFO_WEIGHT.search(s) or _NUMERAL.search(s)):
        return False
    return True


def _information_weight_present(s: str) -> bool:
    if _INFO_WEIGHT.search(s):
        return True
    if _NUMERAL.search(s):
        return True
    if _VERB_LIKE.search(s) and _word_count(s) >= _MIN_WORDS_SEMANTIC:
        return True
    return False


def _is_structural_speech(s: str) -> bool:
    return _STRUCTURAL.search(s) is not None


def _is_filler(s: str) -> bool:
    if _is_backchannel_only(s):
        return True
    if _FILLER_TICS.match(s.strip()):
        return True
    return False


def _is_multi_topic_drift(s: str) -> bool:
    if ";" in s:
        parts = [p.strip() for p in s.split(";") if p.strip()]
        if len(parts) >= 2 and all(_word_count(p) >= 4 for p in parts[:2]):
            return True
    if s.count("—") >= 2 and _word_count(s) > 20:
        return True
    # " A and B and C" topic stacking (weak)
    if s.lower().count(" and ") >= 2 and _word_count(s) > 25:
        return True
    return False


def _is_structural_social(s: str) -> bool:
    return _RE_STRUCTURAL_SOCIAL.search(s) is not None


def _is_generic_non_claim(s: str) -> bool:
    if _RE_GENERIC_UNIVERSAL.search(s):
        return True
    if re.search(r"(?i)small\s+business\s+owner", s) and re.search(
        r"(?i)understand\s+the\s+challenges", s
    ):
        return True
    return False


def _clip_dim(x: int) -> int:
    return max(0, min(_SCORE_MAX_DIM, x))


def _dim_specificity(s: str) -> int:
    wc = _word_count(s)
    toks = {w for w in re.findall(r"[a-z0-9]{4,}", s.lower()) if w not in _BACKCHANNEL_ONLY}
    has_event = re.search(
        r"(?i)\b("
        r"told me|told us|i was|we were|says that|states that|describes|according to|"
        r"meeting|monitored|instructed|prior|during|after|evidence|report"
        r")\b",
        s,
    )
    has_kinds = re.search(
        r"(?i)\b(intelligence|foreign policy|defense|budget|agency|official|infrastructure)\b", s
    )
    if has_event and wc >= 6:
        return 2
    if (has_kinds and wc >= 10 and len(toks) >= 5) or (bool(_NUMERAL.search(s)) and wc >= 6):
        return 2
    if wc >= 6 and len(toks) >= 3:
        return 1
    if re.search(r"(?i)\b(people|things|stuff|challenges?)\b", s) and len(toks) < 4 and wc < 10:
        return 0
    return 1 if wc >= 5 else 0


def _dim_falsifiability(s: str) -> int:
    if re.search(
        r"(?i)\b(told me|told us|says that|states that|describes|according to|study|data|researched)\b", s
    ):
        return 2
    if re.search(r"(?i)\b\$\s*[\d.,]+\b|\b\d+[\d,]*\s*(trillion|billion|million|percent|%)", s, re.IGNORECASE):
        return 2
    if re.search(r"(?i)\b(because|therefore|influenced by|led to|resulted in|more than|less than)\b", s) and _word_count(
        s
    ) >= 8:
        return 2
    if re.search(
        r"(?i)believes? it (?:is|was) alone|greatest threat to|greatest (?:threat|danger) to",
        s,
    ) and not re.search(r"(?i)\b(said|told|report|study|source|according|million|billion)\b", s):
        return 0
    if re.search(r"(?i)\b(i think|i feel that|in my view|it seems|probably|maybe|perhaps)\b", s) and not re.search(
        r"(?i)\b(states|said|told|described|reports)\b", s
    ):
        return 0
    return 1


def _dim_information_density(s: str) -> int:
    wc = _word_count(s)
    toks = [w for w in re.findall(r"[a-z0-9]{3,}", s.lower()) if w not in _BACKCHANNEL_ONLY]
    u = len(set(toks))
    if wc >= 14 and u >= 6:
        return 2
    if wc >= 8 and u >= 4:
        return 1
    if wc < 5:
        return 0
    return 1


def _dim_filler_language(s: str) -> int:
    m = _RE_FILLER_WORDS.findall(s)
    n = len(m)
    if n >= 2 or re.search(r"(?i)\b(folks,|a lot of|very excited|amazing|incredible)\b", s):
        if not re.search(r"(?i)\b(told|states|described|intelligence|monitored)\b", s):
            return 2
    if n == 1:
        return 1
    if re.search(r"(?i)\b(yeah,|right,|like,)\b", s) and _word_count(s) < 10:
        return 1
    return 0


def _dim_abstraction(s: str) -> int:
    if re.search(
        r"(?i)alone in the world|greatest threat|believes? it (?:is|was) alone", s
    ) and not re.search(r"(?i)(trillion|billion|study|told|said|report|according|million)", s):
        return 2
    if re.search(
        r"(?i)national security(?!.+(?:\d{3,}|\$|billion|trillion|study))", s
    ) and re.search(r"(?i)\b(greatest|biggest|only|alone)\b", s):
        return 2
    if re.search(
        r"(?i)foreign policy|intelligence agencies than|mindset|believes? that the world",
        s,
    ):
        return 1
    return 0


def score_claim(s: str) -> Dict[str, Any]:
    """
    v2 rubric: specificity + falsifiability + information_density
    - filler_language - abstraction_level (each 0-2). Reject in gate if total < ``CLAIM_SCORE_MIN``.
    """
    t = _norm_text(s)
    sp = _clip_dim(_dim_specificity(t))
    fa = _clip_dim(_dim_falsifiability(t))
    de = _clip_dim(_dim_information_density(t))
    fl = _clip_dim(_dim_filler_language(t))
    ab = _clip_dim(_dim_abstraction(t))
    total = sp + fa + de - fl - ab
    return {
        "specificity": sp,
        "falsifiability": fa,
        "information_density": de,
        "filler_language": fl,
        "abstraction_level": ab,
        "claim_score": total,
    }


def _infer_claim_kind(s: str, sc: Dict[str, Any]) -> str:
    """Lightweight label for Stage 3+; does not override gate outcome."""
    sl = s.lower()
    if re.search(r"(?i)\b(told me|i was|monitored|describes being|states that|the guest states)\b", sl):
        return "reportative"
    if re.search(r"(?i)\b(trillion|billion|million|defense budget)\b", sl) and re.search(r"\b\d", sl):
        return "focal_numeric_tentative"
    if re.search(
        r"(?i)believes? it|greatest threat|alone in the|national security", sl
    ) and int(sc.get("abstraction_level") or 0) >= 1:
        return "opinion_or_interpretive_tentative"
    if re.search(r"(?i)influenced|mechanism|agencies than elected", sl):
        return "interpretive_assertion"
    return "general"


# Map internal ``R_*`` tokens to stable public audit codes (UPPER_SNAKE).
_INTERNAL_TO_PUBLIC_PRIMARY: Dict[str, str] = {
    R_SEMANTIC_INCOMPLETE: _CODE_LOW_INFO,
    R_NO_INFORMATION_WEIGHT: _CODE_LOW_INFO,
    R_FILLER: _CODE_FILLER,
    R_STRUCTURAL_SPEECH: _CODE_TRANSITION,
    R_MULTI_TOPIC_DRIFT: _CODE_MULTI_TOPIC,
    R_REMOVAL_REDUNDANT: _CODE_CONTEXT_NOISE,
    R_CLAIM_SCORE: _CODE_SCORE_BELOW,
    R_HARD_PODCAST_SCAFFOLD: _CODE_PODCAST_SCAFFOLD,
    R_HARD_META_COMMENTARY: _CODE_TRANSITION,
    R_HARD_PROMO_BUSINESS: _CODE_CONTEXT_NOISE,
    R_HARD_EMOTIONAL_FILLER: _CODE_FILLER,
    R_STRUCTURAL_SOCIAL: _CODE_PODCAST_SCAFFOLD,
    R_GENERIC_NON_CLAIM: _CODE_GENERIC,
    R_NOT_CAUSAL: _CODE_NON_CAUSAL,
}


def _public_score_breakdown(sc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not sc:
        return None
    return {
        "specificity": sc.get("specificity"),
        "falsifiability": sc.get("falsifiability"),
        "information_density": sc.get("information_density"),
        "filler_penalty": sc.get("filler_language"),
        "abstraction_penalty": sc.get("abstraction_level"),
        "total": sc.get("claim_score"),
    }


def _public_codes_reject(primary: str, all_internal: List[str], sc: Optional[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for c in all_internal:
        p = _INTERNAL_TO_PUBLIC_PRIMARY.get(c)
        if p and p not in out:
            out.append(p)
    if primary == R_CLAIM_SCORE and sc:
        if int(sc.get("filler_language", 0) or 0) >= 1 and _CODE_FILLER not in out:
            out.append(_CODE_FILLER)
        if int(sc.get("abstraction_level", 0) or 0) >= 1 and _CODE_HIGH_ABSTRACTION not in out:
            out.append(_CODE_HIGH_ABSTRACTION)
        if int(sc.get("specificity", 0) or 0) == 0 and _CODE_NO_CONCRETE not in out:
            out.append(_CODE_NO_CONCRETE)
        if int(sc.get("falsifiability", 0) or 0) == 0 and _CODE_NON_FALSIFIABLE not in out:
            out.append(_CODE_NON_FALSIFIABLE)
    pp = _INTERNAL_TO_PUBLIC_PRIMARY.get(primary)
    if pp and pp not in out:
        out.insert(0, pp)
    return list(dict.fromkeys(out))


def _public_codes_accept(claim_kind: str, sc: Dict[str, Any]) -> List[str]:
    codes: List[str] = [_CODE_HIGH_INFO]
    if int(sc.get("specificity", 0) or 0) >= 2:
        codes.append(_CODE_SPECIFIC_ATOMIC)
    if int(sc.get("falsifiability", 0) or 0) >= 1:
        codes.append(_CODE_CLEAR_ASSERTION)
    if claim_kind in ("reportative", "focal_numeric_tentative"):
        codes.append(_CODE_TRACEABLE)
    return list(dict.fromkeys(codes))


def _short_explanation(*, decision: str, public_codes: List[str], primary_internal: Optional[str]) -> str:
    if decision == "ACCEPTED":
        return "Passed CLAIM_FILTER rules and score threshold; see reason_codes and score_breakdown."
    return (
        f"Rejected at {STAGE_CLAIM_FILTER}; internal={primary_internal or 'n/a'}; "
        f"codes={', '.join(public_codes[:6])}"
    )


def _build_decision_trace(
    *,
    text: str,
    source_segment_id: str,
    ok: bool,
    primary_internal: str,
    det: Dict[str, Any],
) -> Dict[str, Any]:
    sc = det.get("score") if isinstance(det.get("score"), dict) else None
    if ok:
        kind = str(det.get("claim_kind") or "general")
        pub = _public_codes_accept(kind, sc or {})
        return {
            "text": text,
            "decision": "ACCEPTED",
            "stage": STAGE_CLAIM_FILTER,
            "reason_codes": pub,
            "explanation": _short_explanation(decision="ACCEPTED", public_codes=pub, primary_internal=None),
            "score_breakdown": _public_score_breakdown(sc),
            "claim_score": (sc or {}).get("claim_score"),
            "claim_kind": kind,
            "source_segment_id": source_segment_id,
        }
    air = list(det.get("all_internal_reasons") or [primary_internal])
    pub = _public_codes_reject(primary_internal, air, sc)
    return {
        "text": text,
        "decision": "REJECTED",
        "stage": STAGE_CLAIM_FILTER,
        "reason_codes": pub,
        "explanation": _short_explanation(decision="REJECTED", public_codes=pub, primary_internal=primary_internal),
        "score_breakdown": _public_score_breakdown(sc),
        "claim_score": (sc or {}).get("claim_score"),
        "claim_kind": None,
        "source_segment_id": source_segment_id,
        "rejection_reason": primary_internal,
        "internal_primary": primary_internal,
        "all_internal_reasons": air,
    }


def _slim_for_production(trace: Dict[str, Any], *, is_accept: bool) -> Dict[str, Any]:
    if is_accept:
        return {
            "text": trace["text"],
            "source_segment_id": trace["source_segment_id"],
            "decision": trace["decision"],
            "claim_kind": trace.get("claim_kind"),
        }
    return {
        "text": trace["text"],
        "source_segment_id": trace["source_segment_id"],
        "decision": "REJECTED",
        "reason_codes": trace.get("reason_codes") or [],
        "stage": STAGE_CLAIM_FILTER,
    }


def _hard_rejection(s: str) -> Optional[str]:
    t = s.strip()
    if _HARD_PODCAST.search(t):
        return R_HARD_PODCAST_SCAFFOLD
    if _HARD_META.search(t):
        return R_HARD_META_COMMENTARY
    if _HARD_PROMO.search(t):
        return R_HARD_PROMO_BUSINESS
    if _HARD_EMOTE.match(t):
        return R_HARD_EMOTIONAL_FILLER
    return None


def _removal_redundant_in_context(s: str, transcript_blob: str) -> bool:
    """
    Proxy for “if removed, would understanding change?”.
    If the sentence’s content tokens are already fully covered by the rest, treat as redundant.
    """
    if not transcript_blob or not s:
        return False
    def _tok(x: str) -> set:
        return {w for w in re.findall(r"[a-z0-9]{4,}", x.lower()) if len(w) >= 4}

    ts = _tok(s)
    if not ts or len(ts) < 2:
        return False
    rest = transcript_blob.replace(s, " ", 1)
    tr = _tok(rest)
    if not tr:
        return False
    overlap = len(ts & tr) / max(1, len(ts))
    return overlap >= 0.85 and len(ts) <= 6


def _validate_one(
    text: str,
    *,
    transcript_context: Optional[str] = None,
    use_scoring: bool = True,
) -> Tuple[bool, str, str, Dict[str, Any]]:
    """
    Returns (accepted, primary_internal, primary_internal, details).
    ``details`` includes ``all_internal_reasons`` (full list on reject) and ``score`` when computed.
    """
    s = _norm_text(text)
    details: Dict[str, Any] = {"score": None, "all_internal_reasons": []}
    if not s:
        details["all_internal_reasons"] = [R_SEMANTIC_INCOMPLETE]
        return False, R_SEMANTIC_INCOMPLETE, R_SEMANTIC_INCOMPLETE, details

    h = _hard_rejection(s)
    if h:
        details["all_internal_reasons"] = [h]
        return False, h, h, details

    if _is_structural_social(s):
        details["all_internal_reasons"] = [R_STRUCTURAL_SOCIAL]
        return False, R_STRUCTURAL_SOCIAL, R_STRUCTURAL_SOCIAL, details

    if _is_generic_non_claim(s):
        details["all_internal_reasons"] = [R_GENERIC_NON_CLAIM]
        return False, R_GENERIC_NON_CLAIM, R_GENERIC_NON_CLAIM, details

    reasons: List[str] = []
    if _is_filler(s):
        reasons.append(R_FILLER)
    if _is_structural_speech(s):
        reasons.append(R_STRUCTURAL_SPEECH)
    if not _semantic_complete(s):
        reasons.append(R_SEMANTIC_INCOMPLETE)
    if not _information_weight_present(s):
        reasons.append(R_NO_INFORMATION_WEIGHT)
    if _is_multi_topic_drift(s):
        reasons.append(R_MULTI_TOPIC_DRIFT)
    if transcript_context and _removal_redundant_in_context(s, transcript_context):
        reasons.append(R_REMOVAL_REDUNDANT)

    if reasons:
        order = [
            R_FILLER,
            R_STRUCTURAL_SPEECH,
            R_MULTI_TOPIC_DRIFT,
            R_SEMANTIC_INCOMPLETE,
            R_NO_INFORMATION_WEIGHT,
            R_REMOVAL_REDUNDANT,
        ]
        primary = next((c for c in order if c in reasons), reasons[0])
        details["all_internal_reasons"] = list(reasons)
        if use_scoring:
            details["score"] = score_claim(s)
        return False, primary, primary, details

    sc = score_claim(s)
    details["score"] = sc
    if use_scoring and int(sc.get("claim_score", 0)) < CLAIM_SCORE_MIN:
        details["all_internal_reasons"] = [R_CLAIM_SCORE]
        return False, R_CLAIM_SCORE, R_CLAIM_SCORE, details

    if _claim_require_causal():
        try:
            from .causal_claim import is_causal_claim
        except ImportError:  # pragma: no cover
            from causal_claim import is_causal_claim  # type: ignore
        if not is_causal_claim(s, score_breakdown=sc):
            details["all_internal_reasons"] = [R_NOT_CAUSAL]
            return False, R_NOT_CAUSAL, R_NOT_CAUSAL, details

    details["claim_kind"] = _infer_claim_kind(s, sc)
    details["all_internal_reasons"] = []
    return True, P_PASSED, P_PASSED, details


def _coerce_segment(seg: _Segment, index: int) -> Tuple[str, str]:
    if isinstance(seg, tuple):
        if len(seg) == 2:
            return str(seg[0]), str(seg[1])
        if len(seg) == 1:
            return f"s{index}", str(seg[0])
        return f"s{index}", " ".join(str(x) for x in seg)
    m = seg if isinstance(seg, Mapping) else {}
    sid = m.get("source_segment_id") or m.get("id") or f"s{index}"
    st = m.get("text") or m.get("sentence") or m.get("content") or ""
    return str(sid), str(st)


def filter_claim_candidates(
    segments: Sequence[_Segment],
    *,
    transcript_context: Optional[str] = None,
    use_scoring: bool = True,
    mode: Literal["debug", "production"] = "debug",
    return_internal_debug_trace: bool = False,
) -> Dict[str, Any]:
    """
    Return ``accepted_claims`` and ``rejected_claims`` with a **decision trace** per row.

    * **debug** (default): every row has ``decision`` (``ACCEPTED`` | ``REJECTED``), ``stage``,
      ``reason_codes`` (UPPER_SNAKE), ``explanation``, ``score_breakdown`` (public field names
      with ``filler_penalty`` / ``abstraction_penalty`` / ``total``), ``claim_score``, ``source_segment_id``,
      plus ``rejection_reason`` / ``all_internal_reasons`` on reject for reproducibility.
    * **production**: slimmer dicts (see ``_slim_for_production``). When
      ``return_internal_debug_trace`` is true, the same payload as **debug** is also stored under
      ``_claim_filter_debug_full`` for logging (not for user-facing UIs by default).
    * ``transcript_context`` / ``use_scoring`` — unchanged.
    """
    full_accept: List[Dict[str, Any]] = []
    full_rej: List[Dict[str, Any]] = []
    blob = transcript_context or ""
    for i, seg in enumerate(segments):
        sid, text = _coerce_segment(seg, i)
        nt = _norm_text(text)
        ok, code, _, det = _validate_one(nt, transcript_context=blob, use_scoring=use_scoring)
        tr = _build_decision_trace(
            text=nt, source_segment_id=sid, ok=ok, primary_internal=code, det=det
        )
        if ok:
            full_accept.append(tr)
        else:
            full_rej.append(tr)

    if mode == "debug":
        out: Dict[str, Any] = {
            "accepted_claims": full_accept,
            "rejected_claims": full_rej,
            "stage": STAGE_CLAIM_FILTER,
        }
        if return_internal_debug_trace:
            out["_claim_filter_debug_full"] = {
                "accepted_claims": list(full_accept),
                "rejected_claims": list(full_rej),
            }
        return out

    out_prod: Dict[str, Any] = {
        "accepted_claims": [_slim_for_production(r, is_accept=True) for r in full_accept],
        "rejected_claims": [_slim_for_production(r, is_accept=False) for r in full_rej],
        "stage": STAGE_CLAIM_FILTER,
    }
    if return_internal_debug_trace:
        out_prod["_claim_filter_debug_full"] = {
            "accepted_claims": full_accept,
            "rejected_claims": full_rej,
        }
    return out_prod


def apply_claim_filter_v2_to_brief(
    data: Dict[str, Any],
    *,
    transcript_context: Optional[str] = None,
) -> None:
    """
    In-place: filter ``data[\"claims\"]`` through :func:`filter_claim_candidates`.

    * Off when ``SOAPBOXX_CLAIM_FILTER_V2`` is ``0``/``false``/``off`` (default: **on**).
    * ``SOAPBOXX_CLAIM_FILTER_MODE`` = ``debug`` | ``production`` (default ``production``).
    * ``SOAPBOXX_CLAIM_REQUIRE_CAUSAL`` (default ``1``): reject claims with no explicit mechanism/causal
      language unless falsifiability scored at the top tier (reportative / numeric anchor); see
      :mod:`causal_claim`. Set ``0`` to restore pre–Layer-1 behavior.
    * ``SOAPBOXX_CLAIM_FILTER_DEBUG_TRACE=1`` forces full filter JSON under ``_claim_filter_v2`` in production
      (and ``_claim_filter_debug_full`` on the return payload).
    * Stores summary on ``data[\"_claim_filter_v2\"]``; may append to ``data[\"_quality_warnings\"]`` if all
      claims are dropped.
    """
    v = (os.environ.get("SOAPBOXX_CLAIM_FILTER_V2") or "1").strip().lower()
    if v in ("0", "false", "no", "off"):
        return
    claims = [c for c in (data.get("claims") or []) if isinstance(c, dict)]
    if not claims:
        return
    mode = (os.environ.get("SOAPBOXX_CLAIM_FILTER_MODE") or "production").strip().lower()
    if mode not in ("debug", "production"):
        mode = "production"
    want_trace = (os.environ.get("SOAPBOXX_CLAIM_FILTER_DEBUG_TRACE") or "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    n_in = len(claims)
    segments: List[Dict[str, str]] = []
    for i, c in enumerate(claims):
        cid = str(c.get("id") or f"c{i + 1}")
        segments.append({"source_segment_id": cid, "text": str(c.get("text") or "")})
    out = filter_claim_candidates(
        segments,
        transcript_context=transcript_context,
        mode=mode,  # type: ignore[arg-type]
        return_internal_debug_trace=bool(want_trace or mode == "debug"),
    )
    keep = {str(x.get("source_segment_id")) for x in (out.get("accepted_claims") or []) if isinstance(x, dict)}
    new_claims: List[Dict[str, Any]] = []
    for i, c in enumerate(claims):
        cid = str(c.get("id") or f"c{i + 1}")
        if cid in keep:
            new_claims.append(c)
    data["claims"] = new_claims
    meta: Dict[str, Any] = {
        "n_in": n_in,
        "n_out": len(new_claims),
        "n_rejected": n_in - len(new_claims),
        "mode": mode,
    }
    if mode == "debug" or want_trace:
        meta["filter_output"] = out
    dfull = out.get("_claim_filter_debug_full")
    if dfull is not None:
        meta["debug_full"] = dfull
    data["_claim_filter_v2"] = meta
    if n_in > 0 and len(new_claims) == 0:
        qw = data.get("_quality_warnings")
        if not isinstance(qw, list):
            qw = []
        qw.append(
            "claim_filter_v2 removed all claim rows; consider tuning filters or set SOAPBOXX_CLAIM_FILTER_V2=0 to bypass."
        )
        data["_quality_warnings"] = qw


def explain_verdict(text: str, *, transcript_context: Optional[str] = None) -> Dict[str, Any]:
    """
    Debug helper: rule breakdown + v2 score_breakdown and inferred ``claim_kind``.
    """
    s = _norm_text(text)
    hard = _hard_rejection(s)
    sc = score_claim(s)
    try:
        from .causal_claim import is_causal_claim as _is_causal
    except ImportError:  # pragma: no cover
        from causal_claim import is_causal_claim as _is_causal  # type: ignore
    return {
        "text": s,
        "hard_rejection": hard,
        "structural_social": _is_structural_social(s),
        "generic_non_claim": _is_generic_non_claim(s),
        "semantic_complete": _semantic_complete(s) if not hard else False,
        "information_weight_present": _information_weight_present(s) if not hard else False,
        "not_structural": not _is_structural_speech(s) if not hard else False,
        "not_filler": not _is_filler(s) if not hard else False,
        "not_multi_topic": not _is_multi_topic_drift(s) if not hard else False,
        "removal_not_redundant": not (bool(transcript_context) and _removal_redundant_in_context(s, transcript_context or "")),
        "score_breakdown": sc,
        "claim_kind": _infer_claim_kind(s, sc),
        "is_causal_claim": bool(_is_causal(s, score_breakdown=sc)),
    }


__all__ = [
    "P_PASSED",
    "CLAIM_SCORE_MIN",
    "STAGE_CLAIM_FILTER",
    "R_SEMANTIC_INCOMPLETE",
    "R_NO_INFORMATION_WEIGHT",
    "R_STRUCTURAL_SPEECH",
    "R_FILLER",
    "R_MULTI_TOPIC_DRIFT",
    "R_REMOVAL_REDUNDANT",
    "R_HARD_PODCAST_SCAFFOLD",
    "R_HARD_META_COMMENTARY",
    "R_HARD_PROMO_BUSINESS",
    "R_HARD_EMOTIONAL_FILLER",
    "R_STRUCTURAL_SOCIAL",
    "R_GENERIC_NON_CLAIM",
    "R_CLAIM_SCORE",
    "R_NOT_CAUSAL",
    "score_claim",
    "filter_claim_candidates",
    "apply_claim_filter_v2_to_brief",
    "explain_verdict",
]
