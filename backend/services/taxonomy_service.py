"""Taxonomy + library tree — Day 6."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models import Episode, Podcast, PodcastTaxonomyMap, TaxonomyNode

_TAXONOMY_SEED = (
    Path(__file__).resolve().parents[2] / "data" / "taxonomy_seed.json"
)


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


def _load_seed_tree() -> List[Dict[str, Any]]:
    if not _TAXONOMY_SEED.is_file():
        return []
    payload = json.loads(_TAXONOMY_SEED.read_text(encoding="utf-8"))
    return list(payload.get("tree") or [])


def _pick_leaf_rule(
    podcast_name: str,
    leaf_rules: List[Dict[str, Any]],
    default_leaf_id: str,
) -> str:
    name = (podcast_name or "").lower()
    for rule in leaf_rules:
        tokens = rule.get("contains") or []
        if tokens and any(tok in name for tok in tokens):
            return str(rule["leaf_id"])
    return default_leaf_id


def _synthetic_tree_from_seed(
    podcasts: Dict[int, Podcast],
    ep_counts: Dict[int, int],
    podcast_payload: Callable[[int], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Categorized catalog when taxonomy tables are empty (no seed script required).
    Uses data/taxonomy_seed.json name-matching rules — same shape as DB tree.
    """
    seed = _load_seed_tree()
    if not seed or not podcasts:
        return []

    leaf_rules: List[Dict[str, Any]] = []
    default_leaf_id = ""
    leaf_nodes: Dict[str, Dict[str, Any]] = {}

    def walk_spec(
        spec: Dict[str, Any],
        parent_path: str,
        out_nodes: List[Dict[str, Any]],
    ) -> None:
        nonlocal default_leaf_id
        name = str(spec.get("name") or "").strip()
        node_type = str(spec.get("node_type") or "category")
        path = f"{parent_path}/{name}" if parent_path else name
        children_specs = list(spec.get("children") or [])
        node: Dict[str, Any] = {
            "id": path,
            "name": name,
            "node_type": node_type,
            "children": [],
        }
        if children_specs:
            walk_children = []
            for child in children_specs:
                walk_spec(child, path, walk_children)
            node["children"] = walk_children
            out_nodes.append(node)
            return

        leaf_id = path
        leaf_nodes[leaf_id] = node
        contains = [c.lower() for c in (spec.get("podcast_name_contains") or [])]
        if spec.get("default"):
            default_leaf_id = leaf_id
        if contains or spec.get("default"):
            leaf_rules.append({"leaf_id": leaf_id, "contains": contains})
        node["podcasts"] = []
        out_nodes.append(node)

    roots: List[Dict[str, Any]] = []
    for spec in seed:
        walk_spec(spec, "", roots)

    if not default_leaf_id and leaf_rules:
        default_leaf_id = str(leaf_rules[-1]["leaf_id"])
    if not default_leaf_id and leaf_nodes:
        default_leaf_id = next(iter(leaf_nodes))

    buckets: Dict[str, List[int]] = {lid: [] for lid in leaf_nodes}
    for pid, pod in podcasts.items():
        leaf_id = _pick_leaf_rule(pod.name, leaf_rules, default_leaf_id)
        if leaf_id not in buckets:
            buckets[leaf_id] = []
        buckets[leaf_id].append(int(pid))

    for leaf_id, pids in buckets.items():
        leaf = leaf_nodes.get(leaf_id)
        if not leaf:
            continue
        leaf["podcasts"] = sorted(
            [podcast_payload(pid) for pid in pids],
            key=lambda p: (p.get("name") or "").lower(),
        )

    def prune_empty(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        kept: List[Dict[str, Any]] = []
        for n in nodes:
            kids = prune_empty(n.get("children") or [])
            n["children"] = kids
            if kids or (n.get("podcasts") or []):
                kept.append(n)
        return kept

    return prune_empty(roots)


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

    if not roots:
        return _synthetic_tree_from_seed(podcasts, ep_counts, _podcast_payload)

    tree = [_walk(r) for r in roots]
    mapped_ids = {int(m.podcast_id) for m in maps}
    unmapped = [int(pid) for pid in podcasts if int(pid) not in mapped_ids]
    if unmapped:
        tree.append(
            {
                "id": "unmapped",
                "name": "Library",
                "node_type": "domain",
                "children": [
                    {
                        "id": "unmapped-uncategorized",
                        "name": "Uncategorized",
                        "node_type": "category",
                        "children": [],
                        "podcasts": [_podcast_payload(pid) for pid in unmapped],
                    }
                ],
            }
        )
    return tree
