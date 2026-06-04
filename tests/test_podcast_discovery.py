"""Podcast name search → RSS feed URL (iTunes Search API)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.services.podcast_discovery_service import search_podcasts_by_name


def test_search_requires_min_length():
    with pytest.raises(ValueError, match="at least 2"):
        search_podcasts_by_name("a")


def test_search_maps_feed_url():
    fake_payload = {
        "resultCount": 2,
        "results": [
            {
                "collectionId": 290783428,
                "collectionName": "Planet Money",
                "artistName": "NPR",
                "feedUrl": "https://feeds.npr.org/510289/podcast.xml",
                "primaryGenreName": "Business",
                "trackCount": 900,
                "artworkUrl600": "https://example.com/art.jpg",
            },
            {"collectionName": "No Feed Show", "artistName": "X"},
        ],
    }
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = fake_payload
    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch(
        "backend.services.podcast_discovery_service.httpx.Client",
        return_value=mock_client,
    ):
        hits = search_podcasts_by_name("planet money", limit=10)

    assert len(hits) == 1
    assert hits[0].name == "Planet Money"
    assert hits[0].rss_url.startswith("https://feeds.npr.org")
    assert hits[0].collection_id == 290783428
    assert hits[0].genre == "Business"
    assert hits[0].episode_count == 900
