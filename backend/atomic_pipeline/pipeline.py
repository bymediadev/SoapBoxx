# backend/atomic_pipeline/pipeline.py
"""
Deterministic atomic intelligence pipeline.

Stage order is fixed (see ``run_atomic_pipeline``). Semantic clustering uses lexical + time
proximity by default; swap ``cluster_claims_fn`` for embedding-backed clustering without
changing the envelope schema.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from .schemas import (
    AtomicPipelineEnvelope,
    AudienceAction,
    Claim,
    Clip,
    GuestRecommendation,
    GuestRecommendationReason,
    Insight,
    TopicEdge,
    TopicGraph,
    TopicNode,
    Verification,
)

_PIPELINE_VERSION = "atomic_pipeline/1"

_STOP = frozenset(
    """
    the a an and or but to of in on for with is are was were be been being it this that
    as at by from you your we they their our i he she them his her not do does did can
    could should would have has had theyre there were wasnt
    """.split()
)

_RE_YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
_RE_BRACKET_HMS = re.compile(r"^\s*\[\s*(\d{1,2}):(\d{2}):(\d{2})\s*\]\s*")
_RE_LEADING_TS = re.compile(r"^\s*\[?\s*(\d+\.?\d*)\s*s?\s*\]?\s*", re.I)


def _parse_timestamp_line(line: str) -> Tuple[Optional[float], str]:
    s = line or ""
    m = _RE_BRACKET_HMS.match(s)
    if m:
        h, mi, sec = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return float(h * 3600 + mi * 60 + sec), s[m.end() :].strip()
    m = _RE_LEADING_TS.match(s)
    if not m:
        return None, s
    try:
        return float(m.group(1)), s[m.end() :].strip()
    except ValueError:
        return None, s


def _tokens(s: str) -> Set[str]:
    return set(re.findall(r"[a-z0-9']+", (s or "").lower()))


def _content_tokens(s: str) -> Set[str]:
    return {w for w in _tokens(s) if len(w) > 2 and w not in _STOP}


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _classify_sentence(text: str) -> Tuple[str, str, str]:
    """Return (category, confidence, evidence_basis)."""
    t = (text or "").strip()
    low = t.lower()
    if not t:
        return "unclear", "low", "unknown"
    if "?" in t and len(t.split()) < 24:
        return "rhetorical", "medium", "explicit_transcript"
    if _RE_YEAR.search(t):
        return "historical_fact", "high", "explicit_transcript"
    if any(
        x in low
        for x in (
            "because",
            "means that",
            "really about",
            "i think",
            "we should interpret",
            "signifies",
        )
    ):
        return "interpretation", "medium", "explicit_transcript"
    if any(x in low for x in ("imagine", "we must", "never forget", "lesson is")):
        return "rhetorical", "medium", "explicit_transcript"
    if len(t.split()) < 6:
        return "unclear", "low", "explicit_transcript"
    return "interpretation", "medium", "explicit_transcript"


def extract_atomic_claims(transcript: str, *, max_claims: int = 48) -> List[Claim]:
    """
    Module 1 — split transcript into single-idea sentences with best-effort timestamps.
    Deterministic; does not call an LLM.
    """
    out: List[Claim] = []
    n = 0
    try:
        from ..transcript_structure_extract import strip_youtube_caption_metadata
    except ImportError:  # pragma: no cover
        from transcript_structure_extract import strip_youtube_caption_metadata  # type: ignore
    try:
        from ..episode_quality_gates import claim_structure_score as _claim_shape_score
    except ImportError:  # pragma: no cover
        try:
            from episode_quality_gates import claim_structure_score as _claim_shape_score  # type: ignore
        except ImportError:
            _claim_shape_score = None  # type: ignore[misc, assignment]

    for line in (transcript or "").splitlines():
        ts, rest = _parse_timestamp_line(line)
        line_text = strip_youtube_caption_metadata((rest or "").strip())
        if not line_text:
            continue
        parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", line_text) if s.strip()]
        if not parts:
            parts = [line_text]
        for sent in parts:
            if len(sent.split()) < 5:
                continue
            if _claim_shape_score is not None and float(_claim_shape_score(sent)) < 0.40:
                continue
            try:
                from ..episode_report_v3 import _is_broken_evidence_claim_line as _broken_claim_ln
            except ImportError:  # pragma: no cover
                from episode_report_v3 import _is_broken_evidence_claim_line as _broken_claim_ln  # type: ignore
            if _broken_claim_ln(sent):
                continue
            cat, conf, eb = _classify_sentence(sent)
            n += 1
            stamp = float(ts if ts is not None else 0.0)
            out.append(
                Claim(
                    id=f"a{n}",
                    timestamp=stamp,
                    raw_statement=sent[:2000],
                    category=cat,  # type: ignore[arg-type]
                    confidence=conf,  # type: ignore[arg-type]
                    evidence_basis=eb,  # type: ignore[arg-type]
                )
            )
            if len(out) >= max_claims:
                return out
    return out


def verify_claims(claims: Sequence[Claim]) -> List[Verification]:
    """
    Module 2 — conservative verification without external KB.
    Default: unverified; upgrade only with explicit in-text anchors.
    """
    ver: List[Verification] = []
    for c in claims:
        status = "unverified"
        notes = "No external knowledge base in this pass; default conservative."
        action: str = "fact_check_needed"
        low = c.raw_statement.lower()
        if c.category == "historical_fact" and _RE_YEAR.search(c.raw_statement):
            status = "supported"
            notes = "Year anchor present in transcript sentence; still verify externally for broadcasts."
            action = "keep"
        elif c.category == "rhetorical":
            status = "unverified"
            notes = "Rhetorical fragment — not a factual assertion."
            action = "reframe"
        elif c.category == "unclear":
            status = "unverified"
            notes = "Low signal sentence."
            action = "remove"
        elif "controversial" in low or "probably false" in low:
            status = "disputed"
            notes = "Heuristic flag for disputed framing language."
            action = "fact_check_needed"

        ver.append(
            Verification(
                claim_id=c.id,
                status=status,  # type: ignore[arg-type]
                notes=notes,
                recommended_action=action,  # type: ignore[arg-type]
            )
        )
    return ver


def _verified_claim_ids(claims: Sequence[Claim], verification: Sequence[Verification]) -> Set[str]:
    vmap = {v.claim_id: v for v in verification}
    out: Set[str] = set()
    for c in claims:
        vv = vmap.get(c.id)
        if vv and vv.status == "supported":
            out.add(c.id)
    return out


def _cluster_lexical_time(
    claims: Sequence[Claim],
    allowed: Set[str],
    *,
    sim_threshold: float = 0.12,
    max_time_gap: float = 300.0,
) -> List[List[Claim]]:
    """Greedy clustering: union by time proximity + token overlap (embedding placeholder)."""
    vc = [c for c in claims if c.id in allowed]
    if len(vc) < 2:
        return []
    vc.sort(key=lambda x: (x.timestamp, x.id))
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        if parent.get(x, x) != x:
            parent[x] = find(parent[x])
        return parent.get(x, x)

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    bags = {c.id: _content_tokens(c.raw_statement) for c in vc}
    for i, a in enumerate(vc):
        for b in vc[i + 1 :]:
            if abs(a.timestamp - b.timestamp) > max_time_gap:
                break
            if _jaccard(bags[a.id], bags[b.id]) >= sim_threshold:
                union(a.id, b.id)

    groups: Dict[str, List[Claim]] = defaultdict(list)
    for c in vc:
        groups[find(c.id)].append(c)

    clusters = [sorted(g, key=lambda x: (x.timestamp, x.id)) for g in groups.values() if len(g) >= 2]
    clusters.sort(key=lambda g: g[0].timestamp)
    return clusters


def _topic_label_from_cluster(cluster: Sequence[Claim]) -> str:
    """Cluster centroid label: top content words by frequency (deterministic)."""
    counts: Counter[str] = Counter()
    for c in cluster:
        counts.update(_content_tokens(c.raw_statement))
    if not counts:
        bits = [c.raw_statement.strip() for c in cluster if c.raw_statement.strip()]
        return (bits[0][:80] + "…") if bits else "topic"
    top = [w for w, _ in counts.most_common(5)]
    return " ".join(w.capitalize() for w in top[:4])


def _topic_category(cluster: Sequence[Claim]) -> str:
    cats = [c.category for c in cluster]
    hist = sum(1 for x in cats if x == "historical_fact")
    rhet = sum(1 for x in cats if x == "rhetorical")
    if hist >= max(1, len(cats) // 3):
        return "history"
    if rhet >= len(cats) // 2:
        return "ethics"
    interp = sum(1 for x in cats if x == "interpretation")
    if interp >= len(cats) // 2:
        return "psychology"
    return "other"


def build_topic_graph(
    claims: Sequence[Claim],
    verification: Sequence[Verification],
    *,
    cluster_fn: Optional[Callable[[Sequence[Claim], Set[str]], List[List[Claim]]]] = None,
) -> TopicGraph:
    """
    Module 3 — only ``supported`` claims feed the graph.
    Default clustering: lexical Jaccard + temporal proximity (swap for embeddings).
    """
    allowed = _verified_claim_ids(claims, verification)
    if cluster_fn is None:
        clusters = _cluster_lexical_time(list(claims), allowed)
    else:
        clusters = cluster_fn(list(claims), allowed)
    if not clusters:
        return TopicGraph(nodes=[], edges=[])

    # Weight: claim count + early/repeat mention bonus
    times = [c.timestamp for c in claims if c.id in allowed]
    t_min = min(times) if times else 0.0
    t_max = max(times) if times else 1.0
    span = max(t_max - t_min, 1.0)

    nodes: List[TopicNode] = []
    for i, cl in enumerate(clusters):
        n_claims = len(cl)
        early = 1.0 - ((min(c.timestamp for c in cl) - t_min) / span) if span else 0.5
        w = 0.55 * min(1.0, n_claims / 6.0) + 0.45 * early
        w = min(1.0, max(0.0, round(w, 4)))
        nodes.append(
            TopicNode(
                topic_id=f"t{i+1}",
                label=_topic_label_from_cluster(cl)[:200],
                weight=w,
                category=_topic_category(cl),  # type: ignore[arg-type]
                evidence_claim_ids=[c.id for c in cl],
            )
        )

    edges: List[TopicEdge] = []
    for i in range(len(nodes) - 1):
        a, b = nodes[i], nodes[i + 1]
        rel = "contextualizes"
        if a.category != b.category and {a.category, b.category} <= {"history", "politics"}:
            rel = "conflicts_with"
        elif a.category == b.category:
            rel = "influences"
        edges.append(
            TopicEdge(
                from_topic_id=a.topic_id,
                to_topic_id=b.topic_id,
                relationship=rel,  # type: ignore[arg-type]
            )
        )

    return TopicGraph(nodes=nodes, edges=edges)


def generate_insights(
    claims: Sequence[Claim],
    topic_graph: TopicGraph,
    *,
    verification_present: bool,
) -> List[Insight]:
    """Module 4 — insights only from topic nodes + claim ids."""
    if not verification_present or not topic_graph.nodes:
        return []
    cmap = {c.id: c for c in claims}
    out: List[Insight] = []
    for i, node in enumerate(topic_graph.nodes):
        ids = node.evidence_claim_ids[:12]
        ins_type = "historical" if node.category == "history" else "behavioral"
        stmt = (
            f"Across this thread ({node.label}), the episode ties claims together: "
            + "; ".join(_short(cmap[cid].raw_statement) for cid in ids if cid in cmap)[:360]
        )
        out.append(
            Insight(
                id=f"i{i+1}",
                derived_from_claim_ids=list(ids),
                insight_type=ins_type,  # type: ignore[arg-type]
                insight_statement=stmt,
                applicability="Use this thread to decide what must be verified before clipping.",
            )
        )
    return out


def _short(s: str, n: int = 100) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def _clip_why_and_risk(c: Claim) -> Tuple[str, str]:
    if c.category == "historical_fact":
        return "clarity", "safe"
    if c.category == "rhetorical":
        return "tension", "misleading_if_isolated"
    if "but" in c.raw_statement.lower() or "however" in c.raw_statement.lower():
        return "tension", "contextual"
    return "novelty", "contextual"


def generate_clips(
    claims: Sequence[Claim],
    topic_graph: TopicGraph,
    *,
    verification_present: bool,
    reduce_half: bool,
) -> List[Clip]:
    """Module 5 — prefer higher topic weight; risk-aware."""
    if not verification_present or not topic_graph.nodes:
        return []
    weights = {n.topic_id: n.weight for n in topic_graph.nodes}
    claim_to_topic: Dict[str, str] = {}
    for n in topic_graph.nodes:
        for cid in n.evidence_claim_ids:
            claim_to_topic.setdefault(cid, n.topic_id)

    ranked = sorted(
        claims,
        key=lambda c: (
            -weights.get(claim_to_topic.get(c.id, ""), 0.0),
            -{"high": 3, "medium": 2, "low": 1}.get(c.confidence, 1),
            c.timestamp,
        ),
    )
    max_clips = 6 if not reduce_half else 3
    clips: List[Clip] = []
    for i, c in enumerate(ranked[:max_clips]):
        why, risk = _clip_why_and_risk(c)
        clips.append(
            Clip(
                clip_id=f"cl{i+1}",
                source_claim_id=c.id,
                hook_line=_short(c.raw_statement, 160),
                why_it_works=why,  # type: ignore[arg-type]
                risk_level=risk,  # type: ignore[arg-type]
            )
        )
    return clips


def _gap_type(topic: TopicNode) -> str:
    if topic.category in ("history", "other"):
        return "historical_ambiguity"
    if topic.category == "politics":
        return "interpretation_conflict"
    if topic.category in ("economics",):
        return "system_application"
    if topic.category == "psychology":
        return "theoretical_framing"
    return "lived_experience"


def _guest_type_for_gap(gap: str) -> str:
    return {
        "historical_ambiguity": "historian",
        "interpretation_conflict": "contrarian",
        "system_application": "practitioner",
        "theoretical_framing": "academic",
        "lived_experience": "storyteller",
    }.get(gap, "academic")


def recommend_guests(topic_graph: TopicGraph) -> List[GuestRecommendation]:
    """
    Module 6 — graph-only inputs (topic nodes). No transcript text here.
    At least one contrarian when possible.
    """
    if not topic_graph.nodes:
        return []

    nodes = sorted(topic_graph.nodes, key=lambda n: -n.weight)[:5]
    top3 = nodes[:3]
    out: List[GuestRecommendation] = []

    for i, topic in enumerate(top3):
        gap = _gap_type(topic)
        gt = _guest_type_for_gap(gap)
        # Force one contrarian on second slot if missing
        if i == 1 and not any(r.guest_type == "contrarian" for r in out):
            gt = "contrarian"
            gap = "interpretation_conflict"

        score = round(0.55 + 0.45 * topic.weight, 4)
        out.append(
            GuestRecommendation(
                guest_type=gt,  # type: ignore[arg-type]
                target_topic_id=topic.topic_id,
                relevance_score=score,
                recommendation_reason=GuestRecommendationReason(
                    primary_angle=f"Pressure-test {topic.label} as a cluster ({gap}).",
                    what_they_would_challenge="Whether the cluster’s implied causal story holds under scrutiny.",
                ),
                ideal_questions=[
                    f"What primary source would change how we read {topic.label}?",
                    f"What is the strongest counter-narrative to this cluster?",
                ],
            )
        )

    if not any(r.guest_type == "contrarian" for r in out) and top3:
        t = top3[-1]
        out.append(
            GuestRecommendation(
                guest_type="contrarian",
                target_topic_id=t.topic_id,
                relevance_score=round(0.5 + 0.3 * t.weight, 4),
                recommendation_reason=GuestRecommendationReason(
                    primary_angle="Dedicated contrarian slot — required by pipeline policy.",
                    what_they_would_challenge="Default framing assumptions embedded in the strongest topic clusters.",
                ),
                ideal_questions=[
                    "What would falsify the episode’s implied thesis about this cluster?",
                ],
            )
        )

    return out[:6]


def generate_actions(insights: Sequence[Insight]) -> List[AudienceAction]:
    """Module 7 — testable within 7 days."""
    out: List[AudienceAction] = []
    for i, ins in enumerate(insights[:8]):
        out.append(
            AudienceAction(
                id=f"act{i+1}",
                insight_id=ins.id,
                behavior=(
                    f"Write 5 bullets connecting {ins.insight_type} claims you endorse vs "
                    f"claims you would not quote without verification — for insight {ins.id}."
                )[:500],
                timeframe_days=7,
            )
        )
    return out


def run_atomic_pipeline(
    transcript: str,
    *,
    claims: Optional[Sequence[Claim]] = None,
    verification: Optional[Sequence[Verification]] = None,
    cluster_fn: Optional[Callable[[Sequence[Claim], Set[str]], List[List[Claim]]]] = None,
) -> AtomicPipelineEnvelope:
    """
    Run stages 1–9 in fixed order. Provide ``claims`` / ``verification`` to inject upstream LLM output.

    Global fail-safes:
    - Empty topic graph → guest_recommendations = []
    - Missing verification list → insights + guests blocked
    - Mostly low-confidence claims → clip output halved
    """
    claims_list: List[Claim] = list(claims) if claims is not None else extract_atomic_claims(transcript)
    ver_list: List[Verification] = (
        list(verification) if verification is not None else verify_claims(claims_list)
    )

    verification_present = len(ver_list) > 0 and len(ver_list) == len(claims_list)
    low_share = (
        sum(1 for c in claims_list if c.confidence == "low") / max(len(claims_list), 1)
    )
    reduce_clips = low_share > 0.5

    tg = build_topic_graph(claims_list, ver_list, cluster_fn=cluster_fn)

    insights = (
        generate_insights(claims_list, tg, verification_present=verification_present)
        if verification_present
        else []
    )
    guests = recommend_guests(tg) if tg.nodes else []

    clips = generate_clips(
        claims_list,
        tg,
        verification_present=verification_present,
        reduce_half=reduce_clips,
    )

    actions = generate_actions(insights)

    diagnostics = {
        "pipeline_version": _PIPELINE_VERSION,
        "clustering_backend": "lexical_time_union",
        "verification_present": verification_present,
        "low_confidence_share": round(low_share, 4),
        "clip_reduction_applied": reduce_clips,
        "blocked_insights": not verification_present,
        "blocked_guests_until_verification": not verification_present,
    }

    return AtomicPipelineEnvelope(
        claims=claims_list,
        verification=ver_list,
        topic_graph=tg,
        insights=insights,
        clips=clips,
        guest_recommendations=guests if tg.nodes else [],
        actions=actions,
        diagnostics=diagnostics,
    )


def envelope_to_json(envelope: AtomicPipelineEnvelope) -> dict:
    """Export dict matching Module 8 (diagnostics optional for strict consumers)."""
    d = envelope.model_dump()
    return d
