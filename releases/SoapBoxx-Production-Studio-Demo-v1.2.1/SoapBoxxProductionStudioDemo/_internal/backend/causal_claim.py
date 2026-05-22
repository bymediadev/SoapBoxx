# backend/causal_claim.py
"""Detect explicit causal / mechanism language in claim-shaped text (Layer 1 quality gate)."""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

# Word-boundary phrases: actor/mechanism/outcome glue, not substring noise inside words.
_CAUSAL_RE = re.compile(
    r"(?i)\b("
    r"because|therefore|thereby|consequently|as a result|so that|due to|owing to|"
    r"leads? to|led to|leading to|results? in|resulted in|"
    r"causes?|caused|causing|"
    r"drives?|driving|drove|"
    r"forces?|forcing|forced|"
    r"increases?|increasing|increased|"
    r"reduces?|reducing|reduced|"
    r"improves?|improving|worsens?|undermines?|undermining|"
    r"enables?|enabling|enabled|prevents?|preventing|prevented|"
    r"shifts?|shifting|shifted|reshapes?|reshaping|"
    r"affects?|affecting|affected|"
    r"influences?|influencing|influenced|"
    r"which means|which led|which leads|which drove|which caused|"
    r"means that|implies that|suggests that"
    r")\b"
)


def is_causal_claim(
    text: str,
    *,
    score_breakdown: Optional[Mapping[str, Any]] = None,
    falsifiability: Optional[int] = None,
) -> bool:
    """
    True if the text carries explicit causal/mechanism language **or** already cleared the
    claim_filter_v2 falsifiability rubric at the strongest tier (reportative / numeric anchor).

    The falsifiability bypass keeps evidence-anchored lines like first-person monitoring
    reports and budget figures without forcing awkward "because" insertions.
    """
    if falsifiability is None and score_breakdown is not None:
        try:
            falsifiability = int(score_breakdown.get("falsifiability") or 0)
        except (TypeError, ValueError):
            falsifiability = 0
    if falsifiability is not None and falsifiability >= 2:
        return True
    s = (text or "").strip()
    if not s:
        return False
    return _CAUSAL_RE.search(s) is not None


__all__ = ["is_causal_claim"]
