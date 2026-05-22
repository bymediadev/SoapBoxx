"""RSS ingestion — metadata only (source layer).

Collects podcast + episode data from RSS feeds. Does not transcribe, analyze, or
generate insights.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional

import feedparser
from sqlalchemy.orm import Session

from backend.models import Episode, Podcast
from backend.services.pipeline_status import STATUS_QUEUED, record_event

USER_AGENT = "SoapBoxx-Ingest/1.0 (+https://soapboxx.local)"


@dataclass
class RssEpisodeItem:
    title: str
    description: Optional[str]
    guid: Optional[str]
    audio_url: Optional[str]
    link: Optional[str]
    published_at: Optional[datetime]
    raw_rss: dict[str, Any]


@dataclass
class RssFeedMeta:
    title: str
    description: Optional[str]
    link: Optional[str]


@dataclass
class RssIngestResult:
    podcast_id: int
    created: int
    skipped: int
    episode_ids: List[int]


def _entry_datetime(entry: Any) -> Optional[datetime]:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _entry_audio_url(entry: Any) -> Optional[str]:
    for enc in entry.get("enclosures") or []:
        href = (enc.get("href") or enc.get("url") or "").strip()
        if not href:
            continue
        enc_type = (enc.get("type") or "").lower()
        if not enc_type or enc_type.startswith("audio") or href.endswith(
            (".mp3", ".m4a", ".wav", ".ogg")
        ):
            return href
    for link in entry.get("links") or []:
        if (link.get("type") or "").lower().startswith("audio"):
            href = (link.get("href") or "").strip()
            if href:
                return href
    return (entry.get("link") or "").strip() or None


def _entry_description(entry: Any) -> Optional[str]:
    for key in ("summary", "subtitle", "description", "content"):
        val = entry.get(key)
        if isinstance(val, list) and val:
            val = val[0].get("value") if isinstance(val[0], dict) else val[0]
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _entry_guid(entry: Any) -> Optional[str]:
    for key in ("id", "guid"):
        val = (entry.get(key) or "").strip()
        if val:
            return val
    link = (entry.get("link") or "").strip()
    return link or None


def _serialize_entry(entry: Any) -> dict[str, Any]:
    """Preserve raw feed fields for debugging and later pipeline stages."""
    if hasattr(entry, "as_dict"):
        raw = entry.as_dict()  # type: ignore[attr-defined]
    else:
        raw = dict(entry)
    # Normalize non-JSON-serializable values
    cleaned: dict[str, Any] = {}
    for key, val in raw.items():
        if key in ("published_parsed", "updated_parsed") and val is not None:
            cleaned[key] = list(val[:9]) if hasattr(val, "__getitem__") else val
        else:
            try:
                json.dumps(val)
                cleaned[key] = val
            except (TypeError, ValueError):
                cleaned[key] = str(val)
    return cleaned


def parse_rss_feed(
    source: str,
    *,
    is_url: bool = False,
) -> tuple[RssFeedMeta, List[RssEpisodeItem]]:
    """
    Parse RSS/Atom using feedparser.

    Args:
        source: Feed URL or XML text.
        is_url: When True, fetch and parse remote feed.
    """
    if is_url:
        parsed = feedparser.parse(
            source,
            agent=USER_AGENT,
            request_headers={"User-Agent": USER_AGENT},
        )
    else:
        parsed = feedparser.parse(source)

    if getattr(parsed, "bozo", False) and not parsed.entries:
        exc = getattr(parsed, "bozo_exception", None)
        raise ValueError(f"Invalid or empty RSS feed: {exc or 'parse error'}")

    feed = parsed.feed
    meta = RssFeedMeta(
        title=(feed.get("title") or "").strip() or "Untitled podcast",
        description=(feed.get("subtitle") or feed.get("description") or "").strip()
        or None,
        link=(feed.get("link") or "").strip() or None,
    )

    items: List[RssEpisodeItem] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip() or "Untitled episode"
        items.append(
            RssEpisodeItem(
                title=title,
                description=_entry_description(entry),
                guid=_entry_guid(entry),
                audio_url=_entry_audio_url(entry),
                link=(entry.get("link") or "").strip() or None,
                published_at=_entry_datetime(entry),
                raw_rss=_serialize_entry(entry),
            )
        )
    return meta, items


def parse_rss(xml_text: str) -> tuple[str, Optional[str], List[RssEpisodeItem]]:
    """Backward-compatible helper for tests: (channel_title, channel_link, items)."""
    meta, items = parse_rss_feed(xml_text, is_url=False)
    return meta.title, meta.link, items


def fetch_rss(url: str, *, timeout: int = 30) -> str:
    """Deprecated: prefer feedparser URL parse. Kept for tests that monkeypatch."""
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _find_existing_episode(
    db: Session,
    podcast_id: int,
    item: RssEpisodeItem,
) -> Optional[Episode]:
    if item.guid:
        row = (
            db.query(Episode)
            .filter(Episode.podcast_id == podcast_id, Episode.guid == item.guid)
            .first()
        )
        if row:
            return row

    q = db.query(Episode).filter(
        Episode.podcast_id == podcast_id,
        Episode.title == item.title,
    )
    if item.published_at is not None:
        q = q.filter(Episode.published_at == item.published_at)
    else:
        q = q.filter(Episode.published_at.is_(None))
    return q.first()


def ingest_rss_xml(
    db: Session,
    xml_text: str,
    *,
    rss_url: Optional[str] = None,
    podcast_id: Optional[int] = None,
) -> RssIngestResult:
    """Create or update podcast and episodes from RSS XML. Idempotent."""
    meta, items = parse_rss_feed(xml_text, is_url=False)
    return _ingest_parsed(db, meta, items, rss_url=rss_url, podcast_id=podcast_id)


def ingest_rss_feed(
    db: Session,
    rss_url: str,
    *,
    podcast_id: Optional[int] = None,
) -> RssIngestResult:
    """Fetch RSS URL and ingest podcast + episodes."""
    meta, items = parse_rss_feed(rss_url.strip(), is_url=True)
    return _ingest_parsed(
        db, meta, items, rss_url=rss_url.strip(), podcast_id=podcast_id
    )


def _ingest_parsed(
    db: Session,
    meta: RssFeedMeta,
    items: List[RssEpisodeItem],
    *,
    rss_url: Optional[str],
    podcast_id: Optional[int],
) -> RssIngestResult:
    record_event(
        db,
        "ingest.started",
        f"RSS ingest started{f' for {rss_url}' if rss_url else ''}",
        podcast_id=podcast_id,
        meta={"rss_url": rss_url},
        commit=False,
    )

    if podcast_id is not None:
        podcast = db.get(Podcast, podcast_id)
        if not podcast:
            raise ValueError(f"Podcast {podcast_id} not found")
        if rss_url and not podcast.rss_url:
            podcast.rss_url = rss_url
    else:
        podcast = (
            db.query(Podcast).filter(Podcast.rss_url == rss_url).first()
            if rss_url
            else None
        )
        if not podcast:
            podcast = Podcast(
                name=meta.title,
                description=meta.description,
                rss_url=rss_url,
            )
            db.add(podcast)
            db.flush()
        else:
            if meta.title and podcast.name != meta.title:
                podcast.name = meta.title
            if meta.description:
                podcast.description = meta.description

    created = 0
    skipped = 0
    episode_ids: List[int] = []

    for item in items:
        existing = _find_existing_episode(db, int(podcast.id), item)
        if existing:
            skipped += 1
            episode_ids.append(int(existing.id))
            continue

        guid = item.guid or f"{item.title}|{item.published_at}"
        row = Episode(
            podcast_id=podcast.id,
            title=item.title,
            description=item.description,
            audio_url=item.audio_url,
            published_at=item.published_at,
            guid=guid,
            raw_rss_json=json.dumps(item.raw_rss, ensure_ascii=False),
            pipeline_status=STATUS_QUEUED,
        )
        db.add(row)
        db.flush()
        created += 1
        episode_ids.append(int(row.id))
        record_event(
            db,
            "episode.ingested",
            f"Ingested: {item.title}",
            podcast_id=int(podcast.id),
            episode_id=int(row.id),
            commit=False,
        )

    record_event(
        db,
        "ingest.completed",
        f"RSS ingest finished: {created} created, {skipped} skipped",
        podcast_id=int(podcast.id),
        meta={"created": created, "skipped": skipped, "rss_url": rss_url},
        commit=False,
    )
    db.commit()
    db.refresh(podcast)
    return RssIngestResult(
        podcast_id=int(podcast.id),
        created=created,
        skipped=skipped,
        episode_ids=episode_ids,
    )
