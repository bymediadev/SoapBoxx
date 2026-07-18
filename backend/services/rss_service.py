"""RSS ingestion — metadata only (source layer).

Collects podcast + episode data from RSS feeds. Does not transcribe, analyze, or
generate insights.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
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
    updated: int
    episode_ids: List[int]
    created_episode_ids: List[int]


@dataclass
class RssSyncResult:
    podcasts_checked: int = 0
    episodes_created: int = 0
    episodes_skipped: int = 0
    episodes_updated: int = 0
    episodes_dispatched: int = 0
    failed_podcasts: int = 0
    results: List[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "podcasts_checked": self.podcasts_checked,
            "episodes_created": self.episodes_created,
            "episodes_skipped": self.episodes_skipped,
            "episodes_updated": self.episodes_updated,
            "episodes_dispatched": self.episodes_dispatched,
            "failed_podcasts": self.failed_podcasts,
            "results": self.results,
        }


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


_PLACEHOLDER_TITLE_VALUES = frozenset(
    {"", "untitled", "untitled episode", "untitled podcast", "episode"}
)
_EPISODE_NUMBER_TITLE = re.compile(r"^episode\s*#?\s*\d+\s*$", re.IGNORECASE)


def _is_placeholder_title(title: Optional[str]) -> bool:
    t = (title or "").strip()
    if not t:
        return True
    if t.lower() in _PLACEHOLDER_TITLE_VALUES:
        return True
    return bool(_EPISODE_NUMBER_TITLE.match(t))


def _refresh_episode_from_rss(episode: Episode, item: RssEpisodeItem) -> bool:
    """Fill missing or placeholder episode fields from a fresh RSS item."""
    changed = False

    if _is_placeholder_title(episode.title) and not _is_placeholder_title(item.title):
        episode.title = item.title
        changed = True

    if not (episode.description or "").strip() and item.description:
        episode.description = item.description
        changed = True

    if not (episode.audio_url or "").strip() and item.audio_url:
        episode.audio_url = item.audio_url
        changed = True

    if not (episode.guid or "").strip() and item.guid:
        episode.guid = item.guid
        changed = True

    if episode.published_at is None and item.published_at is not None:
        episode.published_at = item.published_at
        changed = True

    if changed:
        episode.raw_rss_json = json.dumps(item.raw_rss, ensure_ascii=False)

    return changed


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
            if meta.title and (
                _is_placeholder_title(podcast.name) or podcast.name != meta.title
            ):
                if not _is_placeholder_title(meta.title):
                    podcast.name = meta.title
            if meta.description:
                podcast.description = meta.description

    created = 0
    skipped = 0
    updated = 0
    episode_ids: List[int] = []
    created_episode_ids: List[int] = []

    for item in items:
        existing = _find_existing_episode(db, int(podcast.id), item)
        if existing:
            if _refresh_episode_from_rss(existing, item):
                updated += 1
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
        created_episode_ids.append(int(row.id))

    record_event(
        db,
        "ingest.completed",
        f"RSS ingest finished: {created} created, {skipped} skipped, {updated} updated",
        podcast_id=int(podcast.id),
        meta={
            "created": created,
            "skipped": skipped,
            "updated": updated,
            "rss_url": rss_url,
        },
        commit=False,
    )
    db.commit()
    db.refresh(podcast)
    return RssIngestResult(
        podcast_id=int(podcast.id),
        created=created,
        skipped=skipped,
        updated=updated,
        episode_ids=episode_ids,
        created_episode_ids=created_episode_ids,
    )


def dispatch_processing_for_episodes(
    db: Session,
    episode_ids: List[int],
    *,
    trigger: str,
) -> List[int]:
    """Dispatch new episodes into the async processing queue."""
    unique_ids: List[int] = []
    seen: set[int] = set()
    for episode_id in episode_ids:
        if episode_id in seen:
            continue
        seen.add(episode_id)
        unique_ids.append(episode_id)

    if not unique_ids:
        return []

    process_episode_task = None
    dispatch_error: Optional[str] = None
    try:
        from backend.workers.tasks import process_episode_task as celery_process_episode_task

        process_episode_task = celery_process_episode_task
    except Exception as exc:
        dispatch_error = str(exc)

    dispatched_ids: List[int] = []
    for episode_id in unique_ids:
        episode = db.get(Episode, episode_id)
        if not episode:
            continue
        if process_episode_task is None:
            record_event(
                db,
                "pipeline.dispatch_failed",
                f"Auto-processing unavailable: {episode.title}",
                podcast_id=int(episode.podcast_id),
                episode_id=int(episode.id),
                meta={"trigger": trigger, "error": dispatch_error or "dispatch unavailable"},
                commit=False,
            )
            continue
        try:
            process_episode_task.delay(episode_id)
        except Exception as exc:
            record_event(
                db,
                "pipeline.dispatch_failed",
                f"Auto-processing dispatch failed: {episode.title}",
                podcast_id=int(episode.podcast_id),
                episode_id=int(episode.id),
                meta={"trigger": trigger, "error": str(exc)},
                commit=False,
            )
            continue

        dispatched_ids.append(int(episode.id))
        record_event(
            db,
            "episode.processing_dispatched",
            f"Auto-processing started: {episode.title}",
            podcast_id=int(episode.podcast_id),
            episode_id=int(episode.id),
            meta={"trigger": trigger},
            commit=False,
        )

    db.commit()
    return dispatched_ids


def sync_saved_rss_feeds(
    db: Session,
    *,
    dispatch_processing: bool = True,
) -> RssSyncResult:
    """
    Re-ingest every stored RSS feed and optionally dispatch new episodes.

    Safe to run from cron or Celery beat because `ingest_rss_feed()` is idempotent.
    """
    rows = (
        db.query(Podcast)
        .filter(Podcast.rss_url.isnot(None), Podcast.rss_url != "")
        .order_by(Podcast.id)
        .all()
    )

    summary = RssSyncResult(podcasts_checked=len(rows))
    for pod in rows:
        url = (pod.rss_url or "").strip()
        if not url:
            continue

        try:
            ingest_result = ingest_rss_feed(db, url, podcast_id=int(pod.id))
            dispatched_ids = (
                dispatch_processing_for_episodes(
                    db,
                    ingest_result.created_episode_ids,
                    trigger="rss_sync",
                )
                if dispatch_processing and ingest_result.created_episode_ids
                else []
            )
            summary.episodes_created += ingest_result.created
            summary.episodes_skipped += ingest_result.skipped
            summary.episodes_updated += ingest_result.updated
            summary.episodes_dispatched += len(dispatched_ids)
            summary.results.append(
                {
                    "podcast_id": int(pod.id),
                    "podcast_name": pod.name,
                    "created": ingest_result.created,
                    "skipped": ingest_result.skipped,
                    "updated": ingest_result.updated,
                    "dispatched": len(dispatched_ids),
                }
            )
        except Exception as exc:
            db.rollback()
            summary.failed_podcasts += 1
            record_event(
                db,
                "ingest.failed",
                f"RSS sync failed: {pod.name}",
                podcast_id=int(pod.id),
                meta={"rss_url": url, "error": str(exc)},
            )
            summary.results.append(
                {
                    "podcast_id": int(pod.id),
                    "podcast_name": pod.name,
                    "error": str(exc),
                }
            )

    if dispatch_processing:
        from backend.api.config import get_settings
        from backend.services.episode_pipeline_service import drain_pending_pipeline

        settings = get_settings()
        backlog = drain_pending_pipeline(
            db,
            limit=settings.pipeline_sync_batch_size,
            trigger="rss_sync_backlog",
            prefer_celery=True,
        )
        summary.episodes_dispatched += backlog.get("dispatched", 0) + backlog.get(
            "processed", 0
        )
        if backlog.get("mode") != "none":
            summary.results.append({"backlog_drain": backlog})

    return summary
