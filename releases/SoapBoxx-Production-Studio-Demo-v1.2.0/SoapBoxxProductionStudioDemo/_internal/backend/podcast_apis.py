# backend/podcast_apis.py
"""
Podcast-specific API integrations for SoapBoxx
Alternative to Spotify API for podcast-specific features
"""

import os
from typing import Dict, List, Optional

import requests

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print(
        "Warning: python-dotenv not available. Make sure environment variables are set manually."
    )

from error_tracker import track_api_error


class PodcastAPIs:
    """Manages podcast-specific API integrations"""

    def __init__(self):
        self.podchaser_key = os.getenv("PODCHASER_API_KEY")
        self.listen_notes_key = os.getenv("LISTEN_NOTES_API_KEY")
        self.apple_podcasts_key = os.getenv("APPLE_PODCASTS_API_KEY")
        self.google_podcasts_key = os.getenv("GOOGLE_PODCASTS_API_KEY")

    def get_available_apis(self) -> Dict[str, bool]:
        """Get status of available podcast APIs"""
        return {
            "podchaser": bool(self.podchaser_key),
            "listen_notes": bool(self.listen_notes_key),
            "apple_podcasts": bool(self.apple_podcasts_key),
            "google_podcasts": bool(self.google_podcasts_key),
        }

    def search_podcasts(self, query: str, service: str = "podchaser") -> Dict:
        """Search for podcasts using the specified service"""
        if service == "podchaser":
            return self._search_podchaser(query)
        elif service == "listen_notes":
            return self._search_listen_notes(query)
        elif service == "apple_podcasts":
            return self._search_apple_podcasts(query)
        elif service == "google_podcasts":
            return self._search_google_podcasts(query)
        else:
            return {"error": f"Unknown service: {service}"}

    def get_podcast_details(self, podcast_id: str, service: str = "podchaser") -> Dict:
        """Get detailed information about a specific podcast"""
        if service == "podchaser":
            return self._get_podchaser_details(podcast_id)
        elif service == "listen_notes":
            return self._get_listen_notes_details(podcast_id)
        else:
            return {"error": f"Service {service} not supported for details"}

    def get_trending_podcasts(self, service: str = "podchaser") -> Dict:
        """Get trending podcasts from the specified service"""
        if service == "podchaser":
            return self._get_podchaser_trending()
        elif service == "listen_notes":
            return self._get_listen_notes_trending()
        else:
            return {"error": f"Service {service} not supported for trending"}

    def _search_podchaser(self, query: str) -> Dict:
        """Search podcasts using Podchaser API"""
        if not self.podchaser_key:
            return {"error": "Podchaser API key not configured"}

        try:
            url = "https://api.podchaser.com/graphql"
            headers = {
                "Authorization": f"Bearer {self.podchaser_key}",
                "Content-Type": "application/json",
            }

            # GraphQL query for podcast search
            query_graphql = """
            query SearchPodcasts($query: String!) {
                searchPodcasts(query: $query, first: 10) {
                    edges {
                        node {
                            id
                            title
                            description
                            imageUrl
                            websiteUrl
                            categories {
                                name
                            }
                            rating
                            reviewCount
                        }
                    }
                }
            }
            """

            response = requests.post(
                url,
                json={"query": query_graphql, "variables": {"query": query}},
                headers=headers,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "service": "podchaser",
                    "query": query,
                    "results": data.get("data", {})
                    .get("searchPodcasts", {})
                    .get("edges", []),
                }
            else:
                return {"error": f"Podchaser API error: {response.status_code}"}

        except Exception as e:
            track_api_error(
                f"Podchaser search failed: {e}", component="podcast_apis", exception=e
            )
            return {"error": f"Podchaser search failed: {str(e)}"}

    def _search_listen_notes(self, query: str) -> Dict:
        """Search podcasts using Listen Notes API"""
        if not self.listen_notes_key:
            return {"error": "Listen Notes API key not configured"}

        try:
            url = "https://listen-api.listennotes.com/api/v2/search"
            headers = {"X-ListenAPI-Key": self.listen_notes_key}

            params = {"q": query, "type": "podcast", "limit": 10}

            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                return {
                    "service": "listen_notes",
                    "query": query,
                    "results": data.get("results", []),
                }
            else:
                return {"error": f"Listen Notes API error: {response.status_code}"}

        except Exception as e:
            track_api_error(
                f"Listen Notes search failed: {e}",
                component="podcast_apis",
                exception=e,
            )
            return {"error": f"Listen Notes search failed: {str(e)}"}

    def _search_apple_podcasts(self, query: str) -> Dict:
        """Search podcasts using Apple Podcasts API (limited access)"""
        if not self.apple_podcasts_key:
            return {"error": "Apple Podcasts API key not configured"}

        try:
            # Apple Podcasts API has limited public access
            # This is a placeholder implementation
            return {
                "service": "apple_podcasts",
                "query": query,
                "results": [],
                "note": "Apple Podcasts API requires special access. Consider using Podchaser or Listen Notes instead.",
            }
        except Exception as e:
            track_api_error(
                f"Apple Podcasts search failed: {e}",
                component="podcast_apis",
                exception=e,
            )
            return {"error": f"Apple Podcasts search failed: {str(e)}"}

    def _search_google_podcasts(self, query: str) -> Dict:
        """Search podcasts using Google Podcasts API (limited access)"""
        if not self.google_podcasts_key:
            return {"error": "Google Podcasts API key not configured"}

        try:
            # Google Podcasts API has limited public access
            # This is a placeholder implementation
            return {
                "service": "google_podcasts",
                "query": query,
                "results": [],
                "note": "Google Podcasts API requires special access. Consider using Podchaser or Listen Notes instead.",
            }
        except Exception as e:
            track_api_error(
                f"Google Podcasts search failed: {e}",
                component="podcast_apis",
                exception=e,
            )
            return {"error": f"Google Podcasts search failed: {str(e)}"}

    def _get_podchaser_details(self, podcast_id: str) -> Dict:
        """Get podcast details from Podchaser"""
        if not self.podchaser_key:
            return {"error": "Podchaser API key not configured"}

        try:
            url = "https://api.podchaser.com/graphql"
            headers = {
                "Authorization": f"Bearer {self.podchaser_key}",
                "Content-Type": "application/json",
            }

            query_graphql = """
            query GetPodcast($id: ID!) {
                podcast(id: $id) {
                    id
                    title
                    description
                    imageUrl
                    websiteUrl
                    categories {
                        name
                    }
                    rating
                    reviewCount
                    episodes {
                        edges {
                            node {
                                id
                                title
                                description
                                duration
                                publishedAt
                            }
                        }
                    }
                }
            }
            """

            response = requests.post(
                url,
                json={"query": query_graphql, "variables": {"id": podcast_id}},
                headers=headers,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "service": "podchaser",
                    "podcast": data.get("data", {}).get("podcast", {}),
                }
            else:
                return {"error": f"Podchaser API error: {response.status_code}"}

        except Exception as e:
            track_api_error(
                f"Podchaser details failed: {e}", component="podcast_apis", exception=e
            )
            return {"error": f"Podchaser details failed: {str(e)}"}

    def _get_listen_notes_details(self, podcast_id: str) -> Dict:
        """Get podcast details from Listen Notes"""
        if not self.listen_notes_key:
            return {"error": "Listen Notes API key not configured"}

        try:
            url = f"https://listen-api.listennotes.com/api/v2/podcasts/{podcast_id}"
            headers = {"X-ListenAPI-Key": self.listen_notes_key}

            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                return {"service": "listen_notes", "podcast": data}
            else:
                return {"error": f"Listen Notes API error: {response.status_code}"}

        except Exception as e:
            track_api_error(
                f"Listen Notes details failed: {e}",
                component="podcast_apis",
                exception=e,
            )
            return {"error": f"Listen Notes details failed: {str(e)}"}

    def _get_podchaser_trending(self) -> Dict:
        """Get trending podcasts from Podchaser"""
        if not self.podchaser_key:
            return {"error": "Podchaser API key not configured"}

        try:
            url = "https://api.podchaser.com/graphql"
            headers = {
                "Authorization": f"Bearer {self.podchaser_key}",
                "Content-Type": "application/json",
            }

            query_graphql = """
            query GetTrendingPodcasts {
                trendingPodcasts(first: 20) {
                    edges {
                        node {
                            id
                            title
                            description
                            imageUrl
                            rating
                            reviewCount
                        }
                    }
                }
            }
            """

            response = requests.post(
                url, json={"query": query_graphql}, headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "service": "podchaser",
                    "trending": data.get("data", {})
                    .get("trendingPodcasts", {})
                    .get("edges", []),
                }
            else:
                return {"error": f"Podchaser API error: {response.status_code}"}

        except Exception as e:
            track_api_error(
                f"Podchaser trending failed: {e}", component="podcast_apis", exception=e
            )
            return {"error": f"Podchaser trending failed: {str(e)}"}

    def _get_listen_notes_trending(self) -> Dict:
        """Get trending podcasts from Listen Notes"""
        if not self.listen_notes_key:
            return {"error": "Listen Notes API key not configured"}

        try:
            url = "https://listen-api.listennotes.com/api/v2/best_podcasts"
            headers = {"X-ListenAPI-Key": self.listen_notes_key}

            params = {
                "genre_id": 68,  # News & Politics
                "page": 1,
                "region": "us",
                "safe_mode": 0,
            }

            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                return {"service": "listen_notes", "trending": data.get("podcasts", [])}
            else:
                return {"error": f"Listen Notes API error: {response.status_code}"}

        except Exception as e:
            track_api_error(
                f"Listen Notes trending failed: {e}",
                component="podcast_apis",
                exception=e,
            )
            return {"error": f"Listen Notes trending failed: {str(e)}"}

    def get_podcast_analytics(
        self, podcast_id: str, service: str = "podchaser"
    ) -> Dict:
        """Get analytics for a specific podcast"""
        if service == "podchaser":
            return self._get_podchaser_analytics(podcast_id)
        elif service == "listen_notes":
            return self._get_listen_notes_analytics(podcast_id)
        else:
            return {"error": f"Analytics not supported for service: {service}"}

    def _get_podchaser_analytics(self, podcast_id: str) -> Dict:
        """Get analytics from Podchaser"""
        if not self.podchaser_key:
            return {"error": "Podchaser API key not configured"}

        try:
            # This would require additional Podchaser API endpoints
            # For now, return basic analytics
            return {
                "service": "podchaser",
                "podcast_id": podcast_id,
                "analytics": {
                    "rating": "N/A",
                    "review_count": "N/A",
                    "episode_count": "N/A",
                    "note": "Full analytics require additional Podchaser API access",
                },
            }
        except Exception as e:
            track_api_error(
                f"Podchaser analytics failed: {e}",
                component="podcast_apis",
                exception=e,
            )
            return {"error": f"Podchaser analytics failed: {str(e)}"}

    def _get_listen_notes_analytics(self, podcast_id: str) -> Dict:
        """Get analytics from Listen Notes"""
        if not self.listen_notes_key:
            return {"error": "Listen Notes API key not configured"}

        try:
            # Listen Notes provides some analytics in the podcast details
            details = self._get_listen_notes_details(podcast_id)
            if "error" in details:
                return details

            podcast = details.get("podcast", {})
            return {
                "service": "listen_notes",
                "podcast_id": podcast_id,
                "analytics": {
                    "total_episodes": podcast.get("total_episodes", "N/A"),
                    "listen_score": podcast.get("listen_score", "N/A"),
                    "language": podcast.get("language", "N/A"),
                    "country": podcast.get("country", "N/A"),
                },
            }
        except Exception as e:
            track_api_error(
                f"Listen Notes analytics failed: {e}",
                component="podcast_apis",
                exception=e,
            )
            return {"error": f"Listen Notes analytics failed: {str(e)}"}
