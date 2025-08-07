# backend/social_media_scraper.py
"""
Social Media Scraper for SoapBoxx
Uses snscrape to get social media trends and data
"""

import json
import os
import ssl
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import urllib3

# Disable SSL warnings for snscrape compatibility
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Try to import snscrape
try:
    import snscrape.modules.reddit as snreddit
    import snscrape.modules.twitter as sntwitter

    SNSCRAPE_AVAILABLE = True
except ImportError:
    SNSCRAPE_AVAILABLE = False
    print("Warning: snscrape not available. Install with: pip install snscrape")

from error_tracker import track_api_error


class SocialMediaScraper:
    """Social media scraping using snscrape"""

    def __init__(self):
        self.available = SNSCRAPE_AVAILABLE
        if not self.available:
            print(
                "Warning: snscrape not available. Social media features will be limited."
            )

    def get_twitter_trends(self, query: str = "podcast", limit: int = 10) -> Dict:
        """
        Get Twitter trends for a specific query

        Args:
            query: Search query (default: "podcast")
            limit: Number of tweets to return (default: 10)

        Returns:
            Dictionary containing trending tweets
        """
        if not self.available:
            return {"error": "snscrape not available"}

        try:
            tweets = []
            search_query = f"{query} lang:en -is:retweet"

            # Use snscrape to get tweets with SSL context
            scraper = sntwitter.TwitterSearchScraper(search_query)

            for i, tweet in enumerate(scraper.get_items()):
                if i >= limit:
                    break

                tweets.append(
                    {
                        "id": tweet.id,
                        "username": tweet.user.username,
                        "display_name": tweet.user.displayname,
                        "content": tweet.rawContent,
                        "date": tweet.date.isoformat(),
                        "likes": tweet.likeCount,
                        "retweets": tweet.retweetCount,
                        "replies": tweet.replyCount,
                        "url": tweet.url,
                    }
                )

            return {
                "platform": "twitter",
                "query": query,
                "count": len(tweets),
                "tweets": tweets,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            track_api_error(
                f"Twitter scraping failed: {e}",
                component="social_media_scraper",
                exception=e,
            )
            return {"error": f"Twitter scraping failed: {str(e)}"}

    def get_twitter_hashtags(self, hashtag: str = "podcast", limit: int = 10) -> Dict:
        """
        Get tweets with specific hashtag

        Args:
            hashtag: Hashtag to search for (default: "podcast")
            limit: Number of tweets to return (default: 10)

        Returns:
            Dictionary containing hashtag tweets
        """
        if not self.available:
            return {"error": "snscrape not available"}

        try:
            tweets = []
            search_query = f"#{hashtag} lang:en -is:retweet"

            scraper = sntwitter.TwitterSearchScraper(search_query)

            for i, tweet in enumerate(scraper.get_items()):
                if i >= limit:
                    break

                tweets.append(
                    {
                        "id": tweet.id,
                        "username": tweet.user.username,
                        "display_name": tweet.user.displayname,
                        "content": tweet.rawContent,
                        "date": tweet.date.isoformat(),
                        "likes": tweet.likeCount,
                        "retweets": tweet.retweetCount,
                        "replies": tweet.replyCount,
                        "url": tweet.url,
                    }
                )

            return {
                "platform": "twitter",
                "hashtag": hashtag,
                "count": len(tweets),
                "tweets": tweets,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            track_api_error(
                f"Twitter hashtag scraping failed: {e}",
                component="social_media_scraper",
                exception=e,
            )
            return {"error": f"Twitter hashtag scraping failed: {str(e)}"}

    def get_reddit_trends(self, subreddit: str = "podcasts", limit: int = 10) -> Dict:
        """
        Get Reddit trends from a specific subreddit

        Args:
            subreddit: Subreddit name (default: "podcasts")
            limit: Number of posts to return (default: 10)

        Returns:
            Dictionary containing trending Reddit posts
        """
        if not self.available:
            return {"error": "snscrape not available"}

        try:
            posts = []
            search_query = f"subreddit:{subreddit}"

            scraper = snreddit.RedditSearchScraper(search_query)

            for i, post in enumerate(scraper.get_items()):
                if i >= limit:
                    break

                posts.append(
                    {
                        "id": post.id,
                        "title": post.title,
                        "author": post.author,
                        "content": post.selftext if hasattr(post, "selftext") else "",
                        "date": post.date.isoformat(),
                        "upvotes": post.upvoteCount,
                        "downvotes": post.downvoteCount,
                        "comments": post.commentCount,
                        "url": post.url,
                        "subreddit": post.subreddit,
                    }
                )

            return {
                "platform": "reddit",
                "subreddit": subreddit,
                "count": len(posts),
                "posts": posts,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            track_api_error(
                f"Reddit scraping failed: {e}",
                component="social_media_scraper",
                exception=e,
            )
            return {"error": f"Reddit scraping failed: {str(e)}"}

    def get_social_trends_summary(self, platforms: List[str] = None) -> Dict:
        """
        Get a summary of social media trends across platforms

        Args:
            platforms: List of platforms to check (default: ["twitter", "reddit"])

        Returns:
            Dictionary containing trend summaries
        """
        if platforms is None:
            platforms = ["twitter", "reddit"]

        summary = {
            "timestamp": datetime.now().isoformat(),
            "platforms": platforms,
            "trends": {},
        }

        if "twitter" in platforms:
            twitter_trends = self.get_twitter_trends("podcast", limit=5)
            if "error" not in twitter_trends:
                summary["trends"]["twitter"] = {
                    "count": twitter_trends.get("count", 0),
                    "top_tweets": twitter_trends.get("tweets", [])[:3],
                }
            else:
                summary["trends"]["twitter"] = {"error": twitter_trends["error"]}

        if "reddit" in platforms:
            reddit_trends = self.get_reddit_trends("podcasts", limit=5)
            if "error" not in reddit_trends:
                summary["trends"]["reddit"] = {
                    "count": reddit_trends.get("count", 0),
                    "top_posts": reddit_trends.get("posts", [])[:3],
                }
            else:
                summary["trends"]["reddit"] = {"error": reddit_trends["error"]}

        return summary

    def search_social_media(
        self, query: str, platform: str = "twitter", limit: int = 10
    ) -> Dict:
        """
        Search social media for a specific query

        Args:
            query: Search query
            platform: Platform to search ("twitter" or "reddit")
            limit: Number of results to return

        Returns:
            Dictionary containing search results
        """
        if not self.available:
            return {"error": "snscrape not available"}

        if platform.lower() == "twitter":
            return self.get_twitter_trends(query, limit)
        elif platform.lower() == "reddit":
            return self.get_reddit_trends(query, limit)
        else:
            return {"error": f"Unsupported platform: {platform}"}

    def get_trending_topics(self) -> Dict:
        """
        Get trending topics across social media platforms

        Returns:
            Dictionary containing trending topics
        """
        if not self.available:
            return {"error": "snscrape not available"}

        try:
            # Get trending topics from multiple sources
            topics = {
                "twitter": [],
                "reddit": [],
                "timestamp": datetime.now().isoformat(),
            }

            # Twitter trending topics (podcast-related)
            twitter_trends = self.get_twitter_trends("podcast trending", limit=5)
            if "error" not in twitter_trends:
                topics["twitter"] = [
                    {
                        "content": (
                            tweet["content"][:100] + "..."
                            if len(tweet["content"]) > 100
                            else tweet["content"]
                        ),
                        "username": tweet["username"],
                        "likes": tweet["likes"],
                        "url": tweet["url"],
                    }
                    for tweet in twitter_trends.get("tweets", [])
                ]

            # Reddit trending topics
            reddit_trends = self.get_reddit_trends("podcasts", limit=5)
            if "error" not in reddit_trends:
                topics["reddit"] = [
                    {
                        "title": post["title"],
                        "author": post["author"],
                        "upvotes": post["upvotes"],
                        "url": post["url"],
                    }
                    for post in reddit_trends.get("posts", [])
                ]

            return topics

        except Exception as e:
            track_api_error(
                f"Trending topics failed: {e}",
                component="social_media_scraper",
                exception=e,
            )
            return {"error": f"Trending topics failed: {str(e)}"}

    def get_mock_trends(self) -> Dict:
        """
        Get mock trends for testing when real scraping fails

        Returns:
            Dictionary containing mock trend data
        """
        return {
            "twitter": [
                {
                    "content": "Just launched my new podcast! 🎙️ Excited to share insights about #podcasting and #contentcreation",
                    "username": "podcaster_pro",
                    "likes": 42,
                    "url": "https://twitter.com/podcaster_pro/status/123456789",
                },
                {
                    "content": "The future of podcasting is here! AI-powered tools are revolutionizing how we create content. #podcast #AI",
                    "username": "tech_podcast",
                    "likes": 128,
                    "url": "https://twitter.com/tech_podcast/status/123456790",
                },
                {
                    "content": "Tips for new podcasters: 1. Start with a clear niche 2. Be consistent 3. Engage with your audience 4. Quality over quantity",
                    "username": "podcast_guru",
                    "likes": 89,
                    "url": "https://twitter.com/podcast_guru/status/123456791",
                },
            ],
            "reddit": [
                {
                    "title": "What's your favorite podcast editing software?",
                    "author": "podcast_editor",
                    "upvotes": 156,
                    "url": "https://reddit.com/r/podcasts/comments/123456",
                },
                {
                    "title": "Just hit 1000 downloads on my first episode!",
                    "author": "new_podcaster",
                    "upvotes": 89,
                    "url": "https://reddit.com/r/podcasts/comments/123457",
                },
                {
                    "title": "How do you promote your podcast effectively?",
                    "author": "marketing_podcast",
                    "upvotes": 234,
                    "url": "https://reddit.com/r/podcasts/comments/123458",
                },
            ],
            "timestamp": datetime.now().isoformat(),
        }

    def is_available(self) -> bool:
        """Check if snscrape is available"""
        return self.available
