"""
Intelligence ship gate: thin wrapper so tests can patch ``claim_alignment_detail``.

Implementation: ``soapboxx_intelligence_core.assess_brief_intelligence_ship`` (ship math + Ollama).
Alignment scoring: ``semantic_alignment.claim_alignment_detail`` (re-exported here).

Config: ``config/ship_gate.json`` or ``$SOAPBOXX_SHIP_GATE_CONFIG`` (merged by ``load_ship_gate_config``).
"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional

# ``import backend.intelligence_ship_gate`` (preflight) needs package-relative imports; flat
# ``import intelligence_ship_gate`` (tests) needs sibling modules on sys.path.
try:
    from . import soapboxx_intelligence_core as _core
    from .semantic_alignment import claim_alignment_detail
    from .soapboxx_intelligence_core import (
        SHIP_GATE_DEFAULT,
        SUPPORT_RATIO_GATE_MIN,
        SUPPORT_RATIO_REVIEW_MAX,
        THESIS_MIN_WORDS,
        load_ship_gate_config,
    )
except ImportError:  # pragma: no cover - resolved when loaded as a top-level backend/ module
    import soapboxx_intelligence_core as _core
    from semantic_alignment import claim_alignment_detail
    from soapboxx_intelligence_core import (
        SHIP_GATE_DEFAULT,
        SUPPORT_RATIO_GATE_MIN,
        SUPPORT_RATIO_REVIEW_MAX,
        THESIS_MIN_WORDS,
        load_ship_gate_config,
    )


def assess_brief_intelligence_ship(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    mod = sys.modules[__name__]
    return _core.assess_brief_intelligence_ship(brief, alignment_detail_fn=mod.claim_alignment_detail)


__all__ = [
    "assess_brief_intelligence_ship",
    "load_ship_gate_config",
    "claim_alignment_detail",
    "SHIP_GATE_DEFAULT",
    "THESIS_MIN_WORDS",
    "SUPPORT_RATIO_GATE_MIN",
    "SUPPORT_RATIO_REVIEW_MAX",
]
