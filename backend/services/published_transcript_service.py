"""Fetch publisher-hosted transcripts linked from episode descriptions.

Free workaround when Celery/STT is unavailable: many shows (e.g. Lex Fridman)
publish HTML transcripts in the RSS description. Pull those before downloading audio.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

import httpx

USER_AGENT = "SoapBoxx-TranscriptFetch/1.0"
_HREF_RE = re.compile(
    r"""href=["']([^"']+)["']""",
    re.IGNORECASE,
)
_BARE_URL_RE = re.compile(
    r"""https?://[^\s<>\"']+""",
    re.IGNORECASE,
)
_TRANSCRIPT_HINT = re.compile(r"transcript", re.IGNORECASE)


def extract_transcript_urls(description: str | None, *, page_url: str | None = None) -> list[str]:
    """Return likely transcript page URLs from an RSS description / show notes."""
    raw = description or ""
    if not raw.strip():
        return []

    candidates: list[str] = []
    for match in _HREF_RE.finditer(raw):
        href = (match.group(1) or "").strip()
        if not href or href.startswith("#"):
            continue
        abs_url = urljoin(page_url or "", href) if page_url else href
        if _looks_like_transcript_url(abs_url):
            candidates.append(abs_url)

    for match in _BARE_URL_RE.finditer(raw):
        url = match.group(0).rstrip(").,;")
        if _looks_like_transcript_url(url):
            candidates.append(url)

    # Prefer unique, stable order
    seen: set[str] = set()
    out: list[str] = []
    for url in candidates:
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(url)
    return out


def _looks_like_transcript_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    path = (parsed.path or "").lower()
    return bool(_TRANSCRIPT_HINT.search(path) or _TRANSCRIPT_HINT.search(url))


class _EntryContentExtractor(HTMLParser):
    """Collect text inside ``entry-content`` / ``article`` (WordPress-style pages)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._capture_depth = 0
        self._parts: list[str] = []
        # Tags that opened a capture region (so we know when to close).
        self._capture_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        name = tag.lower()
        if name in ("script", "style", "nav", "footer", "header", "noscript"):
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        attr = {k.lower(): (v or "") for k, v in attrs}
        cls = attr.get("class", "")
        if not self._capture_depth and (
            name == "article" or "entry-content" in cls
        ):
            self._capture_depth = 1
            self._capture_tags.append(name)
            return
        if self._capture_depth:
            self._capture_depth += 1

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name in ("script", "style", "nav", "footer", "header", "noscript"):
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if self._capture_depth:
            self._capture_depth -= 1
            if self._capture_depth == 0 and self._capture_tags:
                self._capture_tags.pop()

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not self._capture_depth:
            return
        text = " ".join(data.split())
        if text:
            self._parts.append(text)

    def text(self) -> str:
        return "\n".join(self._parts).strip()


def html_to_transcript_text(html: str) -> str:
    parser = _EntryContentExtractor()
    parser.feed(html or "")
    text = parser.text()
    if len(text) >= 40:
        return text
    # Fallback: crude tag strip if page layout is atypical
    stripped = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html or "")
    stripped = re.sub(r"(?s)<[^>]+>", " ", stripped)
    return " ".join(stripped.split())


def fetch_published_transcript(
    urls: Iterable[str],
    *,
    timeout_seconds: float = 45.0,
) -> Optional[str]:
    """GET the first URL that yields a usable transcript body."""
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(timeout=timeout_seconds, headers=headers, follow_redirects=True) as client:
        for url in urls:
            try:
                res = client.get(url)
                res.raise_for_status()
            except Exception:
                continue
            ctype = (res.headers.get("content-type") or "").lower()
            if "html" not in ctype and "text/plain" not in ctype and ctype:
                # Still try — some CDNs omit type
                pass
            text = html_to_transcript_text(res.text)
            if len(text) >= 40:
                return text
    return None


def resolve_published_transcript(
    description: str | None,
    *,
    page_url: str | None = None,
) -> Optional[str]:
    """Extract transcript links from show notes and fetch the first that works."""
    urls = extract_transcript_urls(description, page_url=page_url)
    if not urls:
        return None
    return fetch_published_transcript(urls)
