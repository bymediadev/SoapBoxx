"""Taxonomy + library tree — Day 6."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models import Episode, Podcast, PodcastTaxonomyMap, TaxonomyNode


def create_taxonomy_node(
    db: Session,
    name: str,
    node_type: str,
    *,
    parent_id: Optional[int] = None,
) -> TaxonomyNode:
    allowed = ("domain", "category", "subcategory")
    if node_type not in allowed:
        raise ValueError(f"node_type must be one of {allowed}")
    row = TaxonomyNode(name=name.strip(), node_type=node_type, parent_id=parent_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def map_podcast_to_taxonomy(
    db: Session, podcast_id: int, taxonomy_node_id: int
) -> None:
    if not db.get(Podcast, podcast_id):
        raise ValueError(f"Podcast {podcast_id} not found")
    if not db.get(TaxonomyNode, taxonomy_node_id):
        raise ValueError(f"Taxonomy node {taxonomy_node_id} not found")
    existing = (
        db.query(PodcastTaxonomyMap)
        .filter(
            PodcastTaxonomyMap.podcast_id == podcast_id,
            PodcastTaxonomyMap.taxonomy_node_id == taxonomy_node_id,
        )
        .first()
    )
    if not existing:
        db.add(
            PodcastTaxonomyMap(
                podcast_id=podcast_id,
                taxonomy_node_id=taxonomy_node_id,
            )
        )
        db.commit()


def get_library_tree(db: Session) -> List[Dict[str, Any]]:
    """Domain → category → subcategory → podcasts → episode counts."""
    nodes = db.query(TaxonomyNode).order_by(TaxonomyNode.id).all()
    by_id = {int(n.id): n for n in nodes}
    children: Dict[int, List[TaxonomyNode]] = {}
    roots: List[TaxonomyNode] = []
    for n in nodes:
        if n.parent_id:
            children.setdefault(int(n.parent_id), []).append(n)
        else:
            roots.append(n)

    maps = db.query(PodcastTaxonomyMap).all()
    podcast_ids_by_node: Dict[int, List[int]] = {}
    for m in maps:
        podcast_ids_by_node.setdefault(int(m.taxonomy_node_id), []).append(
            int(m.podcast_id)
        )

    podcasts = {int(p.id): p for p in db.query(Podcast).all()}
    from sqlalchemy import func, select

    ep_counts: Dict[int, int] = {}
    for pid, cnt in db.execute(
        select(Episode.podcast_id, func.count())
        .group_by(Episode.podcast_id)
    ):
        ep_counts[int(pid)] = int(cnt)

    def _podcast_payload(pid: int) -> Dict[str, Any]:
        p = podcasts[pid]
        return {
            "id": pid,
            "name": p.name,
            "rss_url": p.rss_url,
            "episode_count": ep_counts.get(pid, 0),
        }

    def _walk(node: TaxonomyNode) -> Dict[str, Any]:
        nid = int(node.id)
        out: Dict[str, Any] = {
            "id": nid,
            "name": node.name,
            "node_type": node.node_type,
            "children": [_walk(c) for c in children.get(nid, [])],
        }
        pids = podcast_ids_by_node.get(nid, [])
        if pids:
            out["podcasts"] = [_podcast_payload(pid) for pid in pids]
        return out

    return [_walk(r) for r in roots]
