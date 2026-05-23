#!/usr/bin/env python3
"""Seed taxonomy tree and map podcasts (fixes Domains: 0 on /ui/)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEED_FILE = ROOT / "data" / "taxonomy_seed.json"


def _get_or_create_node(
    db,
    name: str,
    node_type: str,
    parent_id: Optional[int],
) -> Any:
    from backend.models import TaxonomyNode

    q = db.query(TaxonomyNode).filter(
        TaxonomyNode.name == name,
        TaxonomyNode.node_type == node_type,
    )
    if parent_id is None:
        q = q.filter(TaxonomyNode.parent_id.is_(None))
    else:
        q = q.filter(TaxonomyNode.parent_id == parent_id)
    row = q.first()
    if row:
        return row
    from backend.services.taxonomy_service import create_taxonomy_node

    return create_taxonomy_node(db, name, node_type, parent_id=parent_id)


def _walk_tree(
    db,
    nodes: List[Dict[str, Any]],
    parent_id: Optional[int],
    leaf_rules: List[Dict[str, Any]],
    default_leaf_id: List[int],
) -> None:
    for spec in nodes:
        row = _get_or_create_node(db, spec["name"], spec["node_type"], parent_id)
        nid = int(row.id)
        children = spec.get("children") or []
        if children:
            _walk_tree(db, children, nid, leaf_rules, default_leaf_id)
            continue
        if spec.get("default"):
            default_leaf_id.append(nid)
        contains = [c.lower() for c in (spec.get("podcast_name_contains") or [])]
        if contains or spec.get("default"):
            leaf_rules.append({"node_id": nid, "contains": contains})


def _pick_leaf(podcast_name: str, leaf_rules: List[Dict[str, Any]], default_leaf_id: int) -> int:
    name = (podcast_name or "").lower()
    for rule in leaf_rules:
        if rule["contains"] and any(tok in name for tok in rule["contains"]):
            return int(rule["node_id"])
    return default_leaf_id


def main() -> int:
    if not SEED_FILE.is_file():
        print(f"Missing {SEED_FILE}")
        return 1

    payload = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    tree = payload.get("tree") or []

    from backend.api.deps import get_session_factory
    from backend.models import Podcast, PodcastTaxonomyMap, TaxonomyNode
    from backend.services.taxonomy_service import map_podcast_to_taxonomy

    leaf_rules: List[Dict[str, Any]] = []
    default_leaf_ids: List[int] = []

    db = get_session_factory()()
    try:
        _walk_tree(db, tree, None, leaf_rules, default_leaf_ids)
        if not default_leaf_ids:
            print("ERROR: taxonomy_seed.json must include one leaf with default: true")
            return 1
        default_leaf = default_leaf_ids[0]

        mapped = 0
        for podcast in db.query(Podcast).order_by(Podcast.id).all():
            existing = (
                db.query(PodcastTaxonomyMap)
                .filter(PodcastTaxonomyMap.podcast_id == int(podcast.id))
                .first()
            )
            if existing:
                continue
            leaf_id = _pick_leaf(podcast.name, leaf_rules, default_leaf)
            map_podcast_to_taxonomy(db, int(podcast.id), leaf_id)
            mapped += 1
            print(f"  mapped podcast {podcast.id} {podcast.name!r} -> node {leaf_id}")

        domains = db.query(TaxonomyNode).filter(TaxonomyNode.node_type == "domain").count()
        print(f"Done. Domains in DB: {domains}; podcasts newly mapped: {mapped}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
