"""
News API client for Scoop tab (NewsAPI.org).
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import os

import requests

try:
    from .http_verify import requests_verify_arg
except ImportError:
    from http_verify import requests_verify_arg  # type: ignore


def _news_api_key() -> Optional[str]:
    key = (os.getenv("NEWS_API_KEY") or "").strip()
    if not key or key.lower() == "not set":
        return None
    return key


def _format_article_block(article: dict, index: int) -> List[str]:
    title = article.get("title", "No title")
    source = article.get("source", {}).get("name", "Unknown source")
    description = article.get("description", "No description available")
    url = article.get("url", "#")
    published_at = article.get("publishedAt", "Unknown date")
    try:
        date_obj = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
    except Exception:
        formatted_date = published_at

    lines = [
        f"{index}. {title}",
        f"   📰 Source: {source}",
        f"   📅 Published: {formatted_date}",
        f"   📝 {description[:150]}{'...' if len(description) > 150 else ''}",
        f"   🔗 {url}",
        "",
    ]
    return lines


def _http_error_message(response: requests.Response) -> str:
    error_msg = f"❌ News API Error: {response.status_code}"
    if response.status_code == 401:
        error_msg += " - Invalid API key"
    elif response.status_code == 429:
        error_msg += " - Rate limit exceeded"
    else:
        try:
            error_data = response.json()
            error_msg += f" - {error_data.get('message', 'Unknown error')}"
        except Exception:
            error_msg += f" - {response.text[:100]}"
    return error_msg


def format_news_search_results(query: str, articles: list, *, powered_by: bool = True) -> str:
    results = ["📰 News Search Results\n"]
    results.append(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    results.append(f"🔍 Query: {query}")
    results.append(f"📊 Found {len(articles)} articles")
    results.append("─" * 50 + "\n")
    for i, article in enumerate(articles[:5], 1):
        results.extend(_format_article_block(article, i))
    if powered_by:
        results.append("✨ Powered by News API!")
    return "\n".join(results)


def format_latest_headlines_results(articles: list) -> str:
    results = ["📰 Latest News (News API)\n"]
    results.append(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    results.append(f"📊 Total Articles: {len(articles)}\n")
    results.append("─" * 50 + "\n")
    for i, article in enumerate(articles[:5], 1):
        results.extend(_format_article_block(article, i))
    results.append("✨ Powered by News API")
    return "\n".join(results)


def fetch_news_for_query(query: str, *, page_size: int = 10, timeout: float = 10) -> str:
    """Return formatted UI text (success or error message)."""
    api_key = _news_api_key()
    if not api_key:
        return "❌ News API key not configured. Please add NEWS_API_KEY to your .env file."

    url = "https://newsapi.org/v2/everything"
    params = {
        "apiKey": api_key,
        "q": query,
        "pageSize": page_size,
        "language": "en",
        "sortBy": "relevancy",
    }
    try:
        response = requests.get(
            url, params=params, timeout=timeout, verify=requests_verify_arg()
        )
        if response.status_code == 200:
            articles = response.json().get("articles") or []
            if articles:
                return format_news_search_results(query, articles)
            return f"📰 No news articles found for: {query}"
        return _http_error_message(response)
    except requests.exceptions.Timeout:
        return "❌ News API request timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return f"❌ Error fetching news: {e}"
    except Exception as e:
        return f"❌ Error searching news: {e}"


def fetch_latest_headlines(
    *,
    country: str = "us",
    category: str = "technology",
    page_size: int = 10,
    timeout: float = 10,
) -> str:
    """Return formatted UI text for top headlines."""
    api_key = _news_api_key()
    if not api_key:
        return "❌ News API key not configured. Please add NEWS_API_KEY to your .env file."

    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": api_key,
        "country": country,
        "category": category,
        "pageSize": page_size,
        "language": "en",
    }
    try:
        response = requests.get(
            url, params=params, timeout=timeout, verify=requests_verify_arg()
        )
        if response.status_code == 200:
            articles = response.json().get("articles") or []
            if articles:
                return format_latest_headlines_results(articles)
            return "📰 No news articles found. Try again later."
        return _http_error_message(response)
    except requests.exceptions.Timeout:
        return "❌ News API request timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return f"❌ Error fetching news: {e}"
    except Exception as e:
        return f"❌ Unexpected error: {e}"
