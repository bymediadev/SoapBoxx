"""Tests for backend.scoop_news formatting (no HTTP)."""

from __future__ import annotations

from backend.scoop_news import (
    fetch_latest_headlines,
    fetch_news_for_query,
    format_news_search_results,
)


def test_format_news_search_results():
    articles = [
        {
            "title": "Test headline",
            "source": {"name": "Example News"},
            "description": "A short description.",
            "url": "https://example.com/a",
            "publishedAt": "2026-05-18T12:00:00Z",
        }
    ]
    text = format_news_search_results("podcasts", articles)
    assert "Test headline" in text
    assert "Example News" in text
    assert "podcasts" in text


def test_fetch_without_api_key(monkeypatch):
    monkeypatch.delenv("NEWS_API_KEY", raising=False)
    assert "not configured" in fetch_news_for_query("test").lower()
    assert "not configured" in fetch_latest_headlines().lower()
