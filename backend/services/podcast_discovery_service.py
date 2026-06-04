"""Discover podcasts by name and resolve RSS feed URLs (iTunes Search API)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List
import httpx

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
USER_AGENT = "SoapBoxx-Discovery/1.0"


@dataclass
class PodcastSearchHit:
    collection_id: int
    name: str
    artist: str
    rss_url: str
    artwork_url: str | None = None
    genre: str | None = None
    episode_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection_id": self.collection_id,
            "name": self.name,
            "artist": self.artist,
            "rss_url": self.rss_url,
            "artwork_url": self.artwork_url,
            "genre": self.genre,
            "episode_count": self.episode_count,
        }


def search_podcasts_by_name(
    query: str,
    *,
    limit: int = 15,
    timeout_seconds: float = 15.0,
) -> List[PodcastSearchHit]:
    """
    Search Apple Podcasts directory by show name; returns RSS feed URLs when available.

    Uses the public iTunes Search API (no API key). Results without ``feedUrl`` are skipped.
    """
    q = (query or "").strip()
    if len(q) < 2:
        raise ValueError("Search query must be at least 2 characters")
    limit = max(1, min(int(limit), 50))

    params = {
        "term": q,
        "media": "podcast",
        "entity": "podcast",
        "limit": limit,
    }
    headers = {"User-Agent": USER_AGENT}

    with httpx.Client(timeout=timeout_seconds, headers=headers) as client:
        res = client.get(ITUNES_SEARCH_URL, params=params)
        res.raise_for_status()
        payload = res.json()

    hits: List[PodcastSearchHit] = []
    for row in payload.get("results") or []:
        feed = (row.get("feedUrl") or "").strip()
        if not feed:
            continue
        name = (row.get("collectionName") or row.get("trackName") or "").strip()
        if not name:
            continue
        collection_id = row.get("collectionId") or row.get("trackId")
        if collection_id is None:
            continue
        artist = (row.get("artistName") or "").strip() or "Unknown"
        artwork = (row.get("artworkUrl600") or row.get("artworkUrl100") or "").strip() or None
        genre = (row.get("primaryGenreName") or "").strip() or None
        track_count = row.get("trackCount")
        ep_count = int(track_count) if track_count is not None else None
        hits.append(
            PodcastSearchHit(
                collection_id=int(collection_id),
                name=name,
                artist=artist,
                rss_url=feed,
                artwork_url=artwork,
                genre=genre,
                episode_count=ep_count,
            )
        )
    return hits
