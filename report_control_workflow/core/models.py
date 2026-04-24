# report_control_workflow/core/models.py
"""Structured report rows — dataclasses only."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ClaimRow:
    text: str
    evidence: str = ""
    score: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "evidence": self.evidence, "score": round(self.score, 4)}


@dataclass
class ControlReport:
    """Minimal backbone schema enforced by validation."""

    title: str = ""
    thesis: str = ""
    claims: List[ClaimRow] = field(default_factory=list)
    highlights: List[str] = field(default_factory=list)
    clips: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    core_insight: str = ""
    contrarian: str = ""

    def to_minimal_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "thesis": self.thesis,
            "claims": [c.as_dict() for c in self.claims],
            "highlights": list(self.highlights),
            "clips": list(self.clips),
            "actions": list(self.actions),
            "core_insight": (self.core_insight or "").strip(),
            "contrarian": (self.contrarian or "").strip(),
        }

    @classmethod
    def from_minimal_dict(cls, d: Dict[str, Any]) -> "ControlReport":
        claims_in = d.get("claims") or []
        rows: List[ClaimRow] = []
        for x in claims_in:
            if isinstance(x, dict):
                rows.append(
                    ClaimRow(
                        text=str(x.get("text") or "").strip(),
                        evidence=str(x.get("evidence") or "").strip(),
                        score=float(x.get("score") or 0.0),
                    )
                )
        return cls(
            title=str(d.get("title") or "").strip(),
            thesis=str(d.get("thesis") or "").strip(),
            claims=rows,
            highlights=[str(x).strip() for x in (d.get("highlights") or []) if str(x).strip()],
            clips=[str(x).strip() for x in (d.get("clips") or []) if str(x).strip()],
            actions=[str(x).strip() for x in (d.get("actions") or []) if str(x).strip()],
            core_insight=str(d.get("core_insight") or "").strip(),
            contrarian=str(d.get("contrarian") or "").strip(),
        )
