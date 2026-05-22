"""Library tree: category → author → show → episodes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .db import LibraryDB


def get_or_create_podcast(
    *,
    category: str,
    author: str,
    show_title: str,
    db: Optional[LibraryDB] = None,
) -> int:
    database = db or LibraryDB()
    database.init_schema()
    return database.upsert_podcast(
        category=category,
        author=author or "Unknown",
        title=show_title or "Untitled show",
    )


def get_library_tree(db: Optional[LibraryDB] = None) -> List[Dict[str, Any]]:
    """
    Nested structure for UI:

    [ { category, authors: [ { author, shows: [ { id, title, episodes: [...] } ] } ] } ]
    """
    database = db or LibraryDB()
    database.init_schema()
    with database.connect() as conn:
        podcasts = conn.execute(
            "SELECT * FROM podcasts ORDER BY category, author, title"
        ).fetchall()
        episodes = conn.execute(
            """
            SELECT e.id, e.title, e.category, e.created_at, e.podcast_id, e.author,
                   e.processing_status, m.hook_time, m.question_count, m.followup_count
            FROM episodes e
            LEFT JOIN metrics m ON m.episode_id = e.id
            WHERE e.podcast_id IS NOT NULL
            ORDER BY e.created_at DESC
            """
        ).fetchall()

    by_podcast: Dict[int, List[Dict[str, Any]]] = {}
    for ep in episodes:
        pid = ep["podcast_id"]
        if pid is None:
            continue
        by_podcast.setdefault(int(pid), []).append(dict(ep))

    cat_map: Dict[str, Dict[str, Any]] = {}
    for p in podcasts:
        pd = dict(p)
        pid = int(pd["id"])
        cat = str(pd["category"])
        author = str(pd["author"] or "Unknown")
        if cat not in cat_map:
            cat_map[cat] = {"category": cat, "authors": {}}
        authors = cat_map[cat]["authors"]
        if author not in authors:
            authors[author] = {"author": author, "shows": []}
        authors[author]["shows"].append(
            {
                "id": pid,
                "title": pd["title"],
                "rss_url": pd.get("rss_url"),
                "episode_count": len(by_podcast.get(pid, [])),
                "episodes": by_podcast.get(pid, []),
            }
        )

    tree: List[Dict[str, Any]] = []
    for cat in sorted(cat_map.keys()):
        node = cat_map[cat]
        node["authors"] = [
            node["authors"][a] for a in sorted(node["authors"].keys())
        ]
        tree.append(node)
    return tree
