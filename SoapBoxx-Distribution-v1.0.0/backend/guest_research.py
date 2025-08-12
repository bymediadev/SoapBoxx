# backend/guest_research.py
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote, urlparse

import requests

# Try to import error tracker
try:
    from .error_tracker import ErrorCategory, ErrorSeverity, track_api_error
except ImportError:
    try:
        from error_tracker import ErrorCategory, ErrorSeverity, track_api_error
    except ImportError:
        print("Warning: error_tracker not available")

        # Create placeholder classes
        class ErrorCategory:
            AI_API = "ai_api"

        class ErrorSeverity:
            HIGH = "high"

        def track_api_error(message, **kwargs):
            print(f"API error: {message}")


# Try to import OpenAI
try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Warning: OpenAI package not available. Install with: pip install openai")


# Try to import social media scraper for richer fallbacks
try:
    from .social_media_scraper import SocialMediaScraper
except Exception:
    try:
        from social_media_scraper import SocialMediaScraper
    except Exception:
        SocialMediaScraper = None


class GuestResearch:
    def __init__(
        self, openai_api_key: Optional[str] = None, google_cse_id: Optional[str] = None
    ):
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")  # Separate Google API key
        self.google_cse_id = (
            google_cse_id or os.getenv("GOOGLE_CSE_ID") or "0628a50c1bb4e4976"
        )  # Default CSE ID

        if self.api_key and OPENAI_AVAILABLE:
            try:
                # Try new OpenAI client first
                self.client = openai.OpenAI(api_key=self.api_key)
                self.use_new_api = True
            except Exception:
                # Fallback to old API
                openai.api_key = self.api_key
                self.use_new_api = False
        else:
            print("Warning: No OpenAI API key provided. Research will be limited.")
            self.client = None
            self.use_new_api = False

        if self.google_cse_id:
            print(
                f"✅ Google Custom Search Engine configured with ID: {self.google_cse_id[:8]}..."
            )
        else:
            print("Warning: No Google CSE ID provided. Web search will be limited.")

        if not self.google_api_key:
            print("Warning: No Google API key provided. Web search will be limited.")

    def research(
        self, guest_name: str, website: str = None, additional_info: str = None
    ) -> Dict:
        """
        Research a guest and generate talking points and questions

        Args:
            guest_name: Name of the guest
            website: Guest's website or social media
            additional_info: Any additional information about the guest

        Returns:
            Dictionary containing research results
        """
        if not guest_name or not guest_name.strip():
            return {
                "error": "Guest name is required",
                "profile": "",
                "talking_points": [],
                "questions": [],
            }

        if not self.api_key or not OPENAI_AVAILABLE:
            return self._get_fallback_research(guest_name, website)

        try:
            # Gather information about the guest using web search
            web_results = self._search_web(guest_name, website)
            guest_info = self._gather_guest_info(
                guest_name, website, additional_info, web_results
            )

            # Generate research using AI
            research_prompt = self._create_research_prompt(guest_name, guest_info)

            # Call OpenAI API using appropriate method
            if self.use_new_api and self.client:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert podcast researcher and interviewer.",
                        },
                        {"role": "user", "content": research_prompt},
                    ],
                    max_tokens=800,
                    temperature=0.7,
                )
                research_text = response.choices[0].message.content.strip()
            else:
                # Fallback to old API (only if new API is not available)
                try:
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an expert podcast researcher and interviewer.",
                            },
                            {"role": "user", "content": research_prompt},
                        ],
                        max_tokens=800,
                        temperature=0.7,
                    )
                    research_text = response.choices[0].message.content.strip()
                except Exception as old_api_error:
                    print(f"Old API failed: {old_api_error}")
                    return self._get_fallback_research(guest_name, website)

            return self._parse_research_response(research_text, guest_name)

        except Exception as e:
            print(f"Guest research error: {e}")
            track_api_error(
                f"Guest research error: {e}", component="guest_research", exception=e
            )
            return self._get_fallback_research(guest_name, website)

    def search_business(self, company_name: str, search_type: str = "company") -> Dict:
        """
        Search for business and company information including LinkedIn profiles

        Args:
            company_name: Name of the company or business
            search_type: Type of search - "company", "linkedin", "executive", "news"

        Returns:
            Dictionary containing business search results
        """
        if not company_name or not company_name.strip():
            return {
                "error": "Company name is required",
                "results": [],
                "summary": "",
            }

        try:
            results = {
                "company_name": company_name,
                "search_type": search_type,
                "timestamp": datetime.now().isoformat(),
                "results": [],
                "summary": "",
                "linkedin_profiles": [],
                "company_info": {},
                "news": [],
                "social_media": [],
            }

            # Perform different types of searches based on search_type
            if search_type == "company" or search_type == "all":
                # Company website and general info
                company_results = self._search_company_info(company_name)
                results["company_info"] = company_results
                results["results"].extend(company_results.get("web_results", []))

            if search_type == "linkedin" or search_type == "all":
                # LinkedIn profiles and company page
                linkedin_results = self._search_linkedin(company_name)
                results["linkedin_profiles"] = linkedin_results
                results["results"].extend(linkedin_results)

            if search_type == "executive" or search_type == "all":
                # Executive profiles and leadership
                executive_results = self._search_executives(company_name)
                results["results"].extend(executive_results)

            if search_type == "news" or search_type == "all":
                # Recent news and press releases
                news_results = self._search_company_news(company_name)
                results["news"] = news_results
                results["results"].extend(news_results)

            # Generate summary using AI if available
            if self.api_key and OPENAI_AVAILABLE:
                summary = self._generate_business_summary(company_name, results)
                results["summary"] = summary

            return results

        except Exception as e:
            print(f"Business search error: {e}")
            track_api_error(
                f"Business search error: {e}", component="guest_research", exception=e
            )
            return {
                "error": f"Business search failed: {str(e)}",
                "company_name": company_name,
                "results": [],
            }

    def _search_company_info(self, company_name: str) -> Dict:
        """Search for general company information"""
        try:
            # Build search queries for company info
            queries = [
                f'"{company_name}" company',
                f'"{company_name}" about us',
                f'"{company_name}" official website',
                f'"{company_name}" headquarters location',
            ]

            all_results = []
            for query in queries:
                results = self._search_web(query)
                all_results.extend(results)

            # Remove duplicates based on URL
            seen_urls = set()
            unique_results = []
            for result in all_results:
                if result.get("link") not in seen_urls:
                    seen_urls.add(result.get("link"))
                    unique_results.append(result)

            # If we have meaningful results, return them
            if unique_results and not all(r.get("fallback") for r in unique_results):
                return {
                    "web_results": unique_results[:10],  # Limit to top 10 results
                    "company_name": company_name,
                    "search_queries": queries,
                }

            # If all results are fallbacks or no results, enhance with better fallbacks
            print(
                f"🔄 Enhancing company info with better fallbacks for: {company_name}"
            )
            enhanced_fallbacks = self._get_fallback_web_results(
                f"{company_name} company information"
            )

            # Combine any real results with enhanced fallbacks
            combined_results = unique_results + enhanced_fallbacks

            # Remove duplicates and limit
            final_results = []
            seen_keys = set()
            for result in combined_results:
                key = result.get("link") or (result.get("title"), result.get("snippet"))
                if key not in seen_keys:
                    seen_keys.add(key)
                    final_results.append(result)

            return {
                "web_results": final_results[
                    :12
                ],  # Allow more results when using fallbacks
                "company_name": company_name,
                "search_queries": queries,
                "fallback_enhanced": True,
            }

        except Exception as e:
            print(f"Company info search error: {e}")
            # Return enhanced fallbacks even on error
            fallback_results = self._get_fallback_web_results(
                f"{company_name} company information"
            )
            return {
                "web_results": fallback_results,
                "company_name": company_name,
                "error": str(e),
                "fallback_enhanced": True,
            }

    def _search_linkedin(self, company_name: str) -> List[Dict]:
        """Search for LinkedIn profiles and company pages"""
        try:
            # Build LinkedIn-specific search queries
            linkedin_queries = [
                f'"{company_name}" site:linkedin.com',
                f'"{company_name}" CEO site:linkedin.com',
                f'"{company_name}" founder site:linkedin.com',
                f'"{company_name}" executive site:linkedin.com',
            ]

            linkedin_results = []
            for query in linkedin_queries:
                results = self._search_web(query)
                for result in results:
                    if "linkedin.com" in result.get("link", ""):
                        result["type"] = "linkedin_profile"
                        linkedin_results.append(result)

            # If we have real LinkedIn results, return them
            if linkedin_results and not all(
                r.get("fallback") for r in linkedin_results
            ):
                return linkedin_results[:15]  # Limit to top 15 LinkedIn results

            # If all results are fallbacks or no results, enhance with professional fallbacks
            print(
                f"🔄 Enhancing LinkedIn search with professional fallbacks for: {company_name}"
            )
            professional_fallbacks = self._get_fallback_web_results(
                f"{company_name} professional profiles"
            )

            # Filter for professional-related results
            professional_results = []
            for result in professional_fallbacks:
                if any(
                    term in result.get("title", "").lower()
                    or term in result.get("snippet", "").lower()
                    for term in [
                        "profile",
                        "executive",
                        "ceo",
                        "founder",
                        "professional",
                        "linkedin",
                    ]
                ):
                    result["type"] = "professional_profile"
                    result["fallback"] = True
                    professional_results.append(result)

            return professional_results[:15]

        except Exception as e:
            print(f"LinkedIn search error: {e}")
            # Return professional fallbacks even on error
            professional_fallbacks = self._get_fallback_web_results(
                f"{company_name} professional profiles"
            )
            return [
                r
                for r in professional_fallbacks
                if "profile" in r.get("title", "").lower()
                or "executive" in r.get("title", "").lower()
            ][:10]

    def _search_executives(self, company_name: str) -> List[Dict]:
        """Search for executive profiles and leadership information"""
        try:
            # Build executive search queries
            executive_queries = [
                f'"{company_name}" CEO',
                f'"{company_name}" founder',
                f'"{company_name}" executive team',
                f'"{company_name}" leadership',
                f'"{company_name}" board of directors',
            ]

            executive_results = []
            for query in executive_queries:
                results = self._search_web(query)
                for result in results:
                    result["type"] = "executive_info"
                    executive_results.append(result)

            # If we have real executive results, return them
            if executive_results and not all(
                r.get("fallback") for r in executive_results
            ):
                return executive_results[:10]  # Limit to top 10 executive results

            # If all results are fallbacks or no results, enhance with leadership fallbacks
            print(
                f"🔄 Enhancing executive search with leadership fallbacks for: {company_name}"
            )
            leadership_fallbacks = self._get_fallback_web_results(
                f"{company_name} executive leadership"
            )

            # Filter for leadership-related results
            leadership_results = []
            for result in leadership_fallbacks:
                if any(
                    term in result.get("title", "").lower()
                    or term in result.get("snippet", "").lower()
                    for term in [
                        "ceo",
                        "founder",
                        "executive",
                        "leadership",
                        "director",
                        "president",
                        "manager",
                    ]
                ):
                    result["type"] = "executive_info"
                    result["fallback"] = True
                    leadership_results.append(result)

            return leadership_results[:10]

        except Exception as e:
            print(f"Executive search error: {e}")
            # Return leadership fallbacks even on error
            leadership_fallbacks = self._get_fallback_web_results(
                f"{company_name} executive leadership"
            )
            return [
                r
                for r in leadership_fallbacks
                if any(
                    term in r.get("title", "").lower()
                    or term in r.get("snippet", "").lower()
                    for term in ["ceo", "founder", "executive", "leadership"]
                )
            ][:8]

    def _search_company_news(self, company_name: str) -> List[Dict]:
        """Search for recent company news and press releases"""
        try:
            # Build news search queries
            news_queries = [
                f'"{company_name}" news 2024',
                f'"{company_name}" press release',
                f'"{company_name}" announcement',
                f'"{company_name}" recent developments',
            ]

            news_results = []
            for query in news_queries:
                results = self._search_web(query)
                for result in results:
                    result["type"] = "news"
                    news_results.append(result)

            # If we have real news results, return them
            if news_results and not all(r.get("fallback") for r in news_results):
                # Augment with richer fallbacks if needed
                news_results = self._augment_with_fallbacks_if_needed(
                    news_results, f"{company_name} news"
                )
            return news_results[:10]  # Limit to top 10 news results

            # If all results are fallbacks or no results, enhance with news-specific fallbacks
            print(
                f"🔄 Enhancing news search with industry-specific fallbacks for: {company_name}"
            )
            news_fallbacks = self._get_fallback_web_results(
                f"{company_name} news developments"
            )

            # Filter for news-related results and add industry context
            enhanced_news_results = []
            for result in news_fallbacks:
                if any(
                    term in result.get("title", "").lower()
                    or term in result.get("snippet", "").lower()
                    for term in [
                        "news",
                        "press",
                        "announcement",
                        "development",
                        "update",
                        "release",
                    ]
                ):
                    result["type"] = "news"
                    result["fallback"] = True
                    enhanced_news_results.append(result)

            # Add industry-specific news context if we don't have enough results
            if len(enhanced_news_results) < 5:
                industry_context = self._get_industry_news_context(company_name)
                enhanced_news_results.extend(industry_context)

            return enhanced_news_results[:12]  # Allow more results when using fallbacks

        except Exception as e:
            print(f"Company news search error: {e}")
            # Return news fallbacks even on error
            news_fallbacks = self._get_fallback_web_results(
                f"{company_name} news developments"
            )
            return [
                r
                for r in news_fallbacks
                if "news" in r.get("title", "").lower()
                or "press" in r.get("title", "").lower()
            ][:8]

    def _get_industry_news_context(self, company_name: str) -> List[Dict]:
        """Provide industry-specific news context when company news is unavailable"""
        try:
            # Analyze company name for industry hints
            company_lower = company_name.lower()
            industry_context = []

            if any(
                term in company_lower for term in ["rec", "records", "music", "audio"]
            ):
                # Music industry context
                industry_context = [
                    {
                        "title": f"{company_name} - Music Industry Updates",
                        "snippet": f"Music industry companies like {company_name} typically focus on artist development, recording contracts, and music distribution. Industry trends include digital streaming growth, AI-powered music creation, and new revenue models for artists.",
                        "link": "",
                        "displayLink": "industry_analysis",
                        "type": "news",
                        "fallback": True,
                        "source": "music_industry_context",
                    },
                    {
                        "title": f"{company_name} - Recording Industry News",
                        "snippet": f"Recording companies are adapting to changes in music consumption, streaming platforms, and artist discovery. {company_name} may be involved in these industry developments.",
                        "link": "",
                        "displayLink": "industry_analysis",
                        "type": "news",
                        "fallback": True,
                        "source": "recording_industry_context",
                    },
                ]
            elif any(
                term in company_lower
                for term in ["tech", "software", "ai", "digital", "app"]
            ):
                # Technology industry context
                industry_context = [
                    {
                        "title": f"{company_name} - Technology Industry Updates",
                        "snippet": f"Technology companies like {company_name} are driving innovation in software development, AI applications, and digital transformation. Industry trends include cloud computing, AI integration, and cybersecurity.",
                        "link": "",
                        "displayLink": "industry_analysis",
                        "type": "news",
                        "fallback": True,
                        "source": "tech_industry_context",
                    },
                    {
                        "title": f"{company_name} - Software Development News",
                        "snippet": f"Software companies are evolving with trends in agile development, DevOps practices, and user experience design. {company_name} may be contributing to these industry developments.",
                        "link": "",
                        "displayLink": "industry_analysis",
                        "type": "news",
                        "fallback": True,
                        "source": "software_industry_context",
                    },
                ]
            elif any(
                term in company_lower
                for term in ["consulting", "advisory", "services", "solutions"]
            ):
                # Professional services context
                industry_context = [
                    {
                        "title": f"{company_name} - Professional Services Updates",
                        "snippet": f"Professional services companies like {company_name} provide consulting, advisory, and specialized business solutions. Industry trends include digital transformation consulting, sustainability advisory, and remote service delivery.",
                        "link": "",
                        "displayLink": "industry_analysis",
                        "type": "news",
                        "fallback": True,
                        "source": "professional_services_context",
                    },
                    {
                        "title": f"{company_name} - Business Advisory News",
                        "snippet": f"Business advisory firms are adapting to changing market conditions, regulatory requirements, and client needs. {company_name} may be involved in these industry developments.",
                        "link": "",
                        "displayLink": "industry_analysis",
                        "type": "news",
                        "fallback": True,
                        "source": "advisory_industry_context",
                    },
                ]
            else:
                # General business context
                industry_context = [
                    {
                        "title": f"{company_name} - Business Industry Updates",
                        "snippet": f"Companies like {company_name} operate in dynamic business environments with evolving market conditions, regulatory changes, and competitive pressures. Industry trends include digital transformation, sustainability initiatives, and remote work adoption.",
                        "link": "",
                        "displayLink": "industry_analysis",
                        "type": "news",
                        "fallback": True,
                        "source": "general_business_context",
                    },
                    {
                        "title": f"{company_name} - Market Development News",
                        "snippet": f"Businesses are adapting to changing consumer preferences, technological advances, and global market conditions. {company_name} may be involved in these market developments.",
                        "link": "",
                        "displayLink": "industry_analysis",
                        "type": "news",
                        "fallback": True,
                        "source": "market_development_context",
                    },
                ]

            return industry_context

        except Exception as e:
            print(f"Industry context generation failed: {e}")
            return []

    def _generate_business_summary(
        self, company_name: str, search_results: Dict
    ) -> str:
        """Generate an AI-powered summary of business search results"""
        try:
            # Check if we're mostly using fallback results
            fallback_heavy = False
            total_results = 0
            fallback_count = 0

            for section in ["company_info", "linkedin_profiles", "news"]:
                if search_results.get(section):
                    if isinstance(search_results[section], list):
                        section_results = search_results[section]
                    else:
                        section_results = search_results[section].get("web_results", [])

                    total_results += len(section_results)
                    fallback_count += sum(
                        1 for r in section_results if r.get("fallback")
                    )

            if total_results > 0 and fallback_count / total_results > 0.7:
                fallback_heavy = True
                print(f"🔄 Generating fallback-enhanced summary for {company_name}")

            # Prepare context for AI summary
            context_parts = [f"Company: {company_name}"]

            # Add fallback context if we're using many fallbacks
            if fallback_heavy:
                context_parts.append(
                    "Note: This summary is based on enhanced fallback research due to limited web search availability."
                )

            if search_results.get("company_info", {}).get("web_results"):
                context_parts.append("Company Information:")
                for result in search_results["company_info"]["web_results"][:3]:
                    context_parts.append(
                        f"- {result.get('title', 'N/A')}: {result.get('snippet', 'N/A')}"
                    )

            if search_results.get("linkedin_profiles"):
                context_parts.append("LinkedIn Profiles:")
                for profile in search_results["linkedin_profiles"][:3]:
                    context_parts.append(
                        f"- {profile.get('title', 'N/A')}: {profile.get('snippet', 'N/A')}"
                    )

            if search_results.get("news"):
                context_parts.append("Recent News:")
                for news in search_results["news"][:3]:
                    context_parts.append(
                        f"- {news.get('title', 'N/A')}: {news.get('snippet', 'N/A')}"
                    )

            context = "\n".join(context_parts)

            # Create enhanced summary prompt for fallback-heavy results
            if fallback_heavy:
                summary_prompt = f"""
Based on the following research results for {company_name}, provide a comprehensive business summary. 
Note that some information may be based on industry analysis and general business knowledge rather than specific company data.

{context}

Please provide a summary that includes:
1. Company overview and likely business activities (based on name analysis and industry context)
2. Potential leadership structure and executive roles
3. Industry trends and developments that may affect this company
4. Likely company positioning and market focus
5. Potential business opportunities and challenges in their industry

Format the response as a well-structured business summary, clearly indicating when information is based on industry analysis rather than specific company data.
"""
            else:
                summary_prompt = f"""
Based on the following search results for {company_name}, provide a comprehensive business summary:

{context}

Please provide a summary that includes:
1. Company overview and main business activities
2. Key leadership and notable executives
3. Recent news and developments
4. Company size and industry positioning
5. Notable achievements or challenges

Format the response as a well-structured business summary.
"""

            # Call OpenAI API
            if self.use_new_api and self.client:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert business analyst and researcher. When information is limited, provide industry context and educated insights based on company name analysis and industry knowledge.",
                        },
                        {"role": "user", "content": summary_prompt},
                    ],
                    max_tokens=600,  # Allow more tokens for fallback summaries
                    temperature=0.7,
                )
                summary = response.choices[0].message.content.strip()
            else:
                # Fallback to old API
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert business analyst and researcher. When information is limited, provide industry context and educated insights based on company name analysis and industry knowledge.",
                        },
                        {"role": "user", "content": summary_prompt},
                    ],
                    max_tokens=600,  # Allow more tokens for fallback summaries
                    temperature=0.7,
                )
                summary = response.choices[0].message.content.strip()

            return summary

        except Exception as e:
            print(f"Business summary generation error: {e}")
            # Provide a basic fallback summary
            return f"""**Business Summary: {company_name}**

**1. Company Overview and Main Business Activities**
{company_name} is a company operating in an industry that requires further research. Based on the company name, they may be involved in business activities related to their industry sector.

**2. Key Leadership and Notable Executives**
Information regarding {company_name}'s key leadership team and notable executives requires additional research through professional networks and business databases.

**3. Recent News and Developments**
Recent news, press releases, or announcements related to {company_name} are not currently available through standard web search methods.

**4. Company Size and Industry Positioning**
Details about {company_name}'s company size, revenue, employee count, or industry positioning require access to business databases or direct company contact.

**5. Notable Achievements or Challenges**
Information about {company_name}'s notable achievements or challenges is not currently available through standard research methods.

*Note: This summary was generated due to limited web search availability. For more detailed information, consider contacting the company directly or consulting business databases.*"""

    def _search_web(self, query: str, website: str = None) -> List[Dict]:
        """Search the web for information using Google CSE with enhanced error handling"""
        if not self.google_cse_id or not self.google_api_key:
            print("Web search not available: Missing Google CSE ID or API key")
            return []

        try:
            # Build search query
            search_terms = [query]
            if website:
                domain = urlparse(website).netloc if website else ""
                if domain:
                    search_terms.append(f"site:{domain}")

            final_query = " ".join(search_terms)
            encoded_query = quote(final_query)

            # Google Custom Search API endpoint
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.google_api_key,
                "cx": self.google_cse_id,
                "q": final_query,
                "num": 5,  # Limit to 5 results
            }

            response = requests.get(url, params=params, timeout=10)

            # Enhanced error handling
            if response.status_code == 403:
                print(
                    f"⚠️ Google API 403 Forbidden - API key may be invalid or quota exceeded"
                )
                print(f"   Query: {final_query}")
                print(f"   CSE ID: {self.google_cse_id[:8]}...")
                print(
                    f"   API Key: {self.google_api_key[:10]}..."
                    if self.google_api_key
                    else "   API Key: Not set"
                )
                track_api_error(
                    f"Google API 403 Forbidden for query: {final_query}",
                    component="guest_research",
                    severity=ErrorSeverity.MEDIUM,
                )
                return self._get_fallback_web_results(query)

            elif response.status_code == 429:
                print(f"⚠️ Google API 429 Rate Limited - Too many requests")
                track_api_error(
                    f"Google API 429 Rate Limited for query: {final_query}",
                    component="guest_research",
                    severity=ErrorSeverity.MEDIUM,
                )
                return self._get_fallback_web_results(query)

            elif response.status_code != 200:
                print(f"⚠️ Google API Error {response.status_code}: {response.text}")
                track_api_error(
                    f"Google API Error {response.status_code}: {response.text}",
                    component="guest_research",
                    severity=ErrorSeverity.MEDIUM,
                )
                return self._get_fallback_web_results(query)

            data = response.json()
            results = []

            if "items" in data:
                for item in data["items"]:
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "link": item.get("link", ""),
                            "displayLink": item.get("displayLink", ""),
                        }
                    )

            print(f"✅ Found {len(results)} web results for query: {query}")
            return results

        except requests.exceptions.Timeout:
            print(f"⚠️ Web search timeout for query: {query}")
            track_api_error(
                f"Web search timeout for query: {query}",
                component="guest_research",
                severity=ErrorSeverity.MEDIUM,
            )
            return self._get_fallback_web_results(query)

        except requests.exceptions.RequestException as e:
            print(f"⚠️ Web search request error: {e}")
            track_api_error(
                f"Web search request error: {e}",
                component="guest_research",
                severity=ErrorSeverity.MEDIUM,
            )
            return self._get_fallback_web_results(query)

        except Exception as e:
            print(f"Web search error: {e}")
            track_api_error(
                f"Web search error: {e}", component="guest_research", exception=e
            )
            return self._get_fallback_web_results(query)

    def _get_fallback_web_results(self, query: str) -> List[Dict]:
        """Provide richer fallback results when web search fails."""
        print(f"🔄 Using enhanced fallback research for: {query}")

        results: List[Dict] = []

        # 1) Enhanced Wikipedia search with better parsing
        try:
            # Try open search first
            wiki_resp = requests.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "opensearch",
                    "search": query,
                    "limit": 5,
                    "namespace": 0,
                    "format": "json",
                },
                timeout=8,
            )
            if wiki_resp.status_code == 200:
                data = wiki_resp.json()
                if isinstance(data, list) and len(data) >= 4:
                    titles = data[1] or []
                    snippets = data[2] or []
                    links = data[3] or []
                    for t, s, l in zip(titles, snippets, links):
                        if l and t and s:
                            results.append(
                                {
                                    "title": t,
                                    "snippet": s[:200] + "..." if len(s) > 200 else s,
                                    "link": l,
                                    "displayLink": "wikipedia.org",
                                    "fallback": True,
                                    "source": "wikipedia",
                                }
                            )

            # If no results from open search, try page content search
            if not results:
                wiki_content_resp = requests.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "format": "json",
                        "list": "search",
                        "srsearch": query,
                        "srlimit": 3,
                    },
                    timeout=8,
                )
                if wiki_content_resp.status_code == 200:
                    content_data = wiki_content_resp.json()
                    if "query" in content_data and "search" in content_data["query"]:
                        for item in content_data["query"]["search"][:3]:
                            results.append(
                                {
                                    "title": item.get("title", query),
                                    "snippet": item.get("snippet", "")
                                    .replace('<span class="searchmatch">', "")
                                    .replace("</span>", "")[:200]
                                    + "...",
                                    "link": f"https://en.wikipedia.org/wiki/{item.get('title', '').replace(' ', '_')}",
                                    "displayLink": "wikipedia.org",
                                    "fallback": True,
                                    "source": "wikipedia_content",
                                }
                            )
        except Exception as e:
            print(f"Fallback Wikipedia search failed: {e}")

        # 2) Company domain and business info fallback
        try:
            # Try to extract company name and search for business info
            company_terms = query.lower().split()
            if "rec" in company_terms or "records" in company_terms:
                # This looks like a record company
                results.append(
                    {
                        "title": f"{query} - Music Industry Company",
                        "snippet": f"{query} appears to be a music recording company or label. Music industry companies typically focus on artist development, recording, and music distribution.",
                        "link": "",
                        "displayLink": "industry_analysis",
                        "fallback": True,
                        "source": "industry_knowledge",
                    }
                )
            elif any(
                term in company_terms for term in ["tech", "software", "ai", "digital"]
            ):
                results.append(
                    {
                        "title": f"{query} - Technology Company",
                        "snippet": f"{query} appears to be a technology company. Tech companies typically focus on software development, AI, or digital services.",
                        "link": "",
                        "displayLink": "industry_analysis",
                        "fallback": True,
                        "source": "industry_knowledge",
                    }
                )
            elif any(
                term in company_terms for term in ["consulting", "advisory", "services"]
            ):
                results.append(
                    {
                        "title": f"{query} - Professional Services",
                        "snippet": f"{query} appears to be a professional services company, likely providing consulting, advisory, or specialized business services.",
                        "link": "",
                        "displayLink": "industry_analysis",
                        "fallback": True,
                        "source": "industry_knowledge",
                    }
                )
        except Exception as e:
            print(f"Industry analysis fallback failed: {e}")

        # 3) Enhanced social media signals (if available)
        try:
            if SocialMediaScraper is not None:
                sm = SocialMediaScraper()

                # Twitter trends
                try:
                    tw = sm.get_twitter_trends(query, limit=3)
                    for tweet in tw.get("tweets", [])[:3]:
                        if tweet.get("content") and len(tweet.get("content", "")) > 20:
                            results.append(
                                {
                                    "title": f"Twitter: @{tweet.get('username','user')}",
                                    "snippet": (
                                        tweet.get("content", "")[:150] + "..."
                                        if len(tweet.get("content", "")) > 150
                                        else tweet.get("content", "")
                                    ),
                                    "link": tweet.get("url", ""),
                                    "displayLink": "twitter.com",
                                    "fallback": True,
                                    "source": "twitter",
                                }
                            )
                except Exception as e:
                    print(f"Twitter fallback failed: {e}")

                # Reddit trends
                try:
                    rd = sm.get_reddit_trends(query, limit=3)
                    for post in rd.get("posts", [])[:3]:
                        if post.get("content") and len(post.get("content", "")) > 20:
                            results.append(
                                {
                                    "title": f"Reddit: {post.get('title', 'Discussion')}",
                                    "snippet": (
                                        post.get("content", "")[:150] + "..."
                                        if len(post.get("content", "")) > 150
                                        else post.get("content", "")
                                    ),
                                    "link": post.get("url", ""),
                                    "displayLink": "reddit.com",
                                    "fallback": True,
                                    "source": "reddit",
                                }
                            )
                except Exception as e:
                    print(f"Reddit fallback failed: {e}")
        except Exception as e:
            print(f"Fallback social search failed: {e}")

        # 4) Business directory fallback
        try:
            # Try to find business listings
            business_queries = [
                f"{query} company profile",
                f"{query} business information",
                f"{query} about us",
            ]

            for bq in business_queries:
                # Simulate finding business directory info
                results.append(
                    {
                        "title": f"{query} - Company Profile",
                        "snippet": f"Business information for {query}. Company details, contact information, and business activities may be available through business directories or company websites.",
                        "link": "",
                        "displayLink": "business_directory",
                        "fallback": True,
                        "source": "business_directory",
                    }
                )
                break  # Just add one business directory result
        except Exception as e:
            print(f"Business directory fallback failed: {e}")

        # 5) Enhanced placeholder if still no meaningful results
        if not results or all(len(r.get("snippet", "")) < 30 for r in results):
            # Provide more specific fallback based on query type
            if "news" in query.lower():
                results.append(
                    {
                        "title": f"Recent News for {query}",
                        "snippet": f"Searching for recent news, press releases, and announcements related to {query}. News sources may include industry publications, press releases, and business updates.",
                        "link": "",
                        "displayLink": "news_search",
                        "fallback": True,
                        "source": "news_fallback",
                    }
                )
            elif "linkedin" in query.lower() or "executive" in query.lower():
                results.append(
                    {
                        "title": f"Professional Profiles for {query}",
                        "snippet": f"Searching for professional profiles, executive information, and leadership details for {query}. This may include LinkedIn profiles, company leadership pages, and professional networks.",
                        "link": "",
                        "displayLink": "professional_search",
                        "fallback": True,
                        "source": "professional_fallback",
                    }
                )
            else:
                results.append(
                    {
                        "title": f"Company Research for {query}",
                        "snippet": f"Comprehensive business research for {query} including company information, industry analysis, recent developments, and professional profiles. Research sources may include business databases, news outlets, and professional networks.",
                        "link": "",
                        "displayLink": "business_research",
                        "fallback": True,
                        "source": "comprehensive_fallback",
                    }
                )

        print(f"✅ Generated {len(results)} enhanced fallback results for: {query}")
        return results[:12]  # Allow more fallback results

    def _augment_with_fallbacks_if_needed(
        self, items: List[Dict], query: str
    ) -> List[Dict]:
        """If items are empty or only placeholders, add richer fallback items and dedupe by link."""
        if not items or all(it.get("fallback") for it in items):
            print(f"🔄 Augmenting results with enhanced fallbacks for: {query}")
            extra = self._get_fallback_web_results(query)
            seen = set()
            merged: List[Dict] = []

            # First add any non-fallback items
            for it in items:
                if not it.get("fallback"):
                    link = it.get("link")
                    key = link or (it.get("title"), it.get("snippet"))
                    if key not in seen:
                        seen.add(key)
                        merged.append(it)

            # Then add enhanced fallback items
            for it in extra:
                link = it.get("link")
                key = link or (it.get("title"), it.get("snippet"))
                if key not in seen:
                    seen.add(key)
                    merged.append(it)

            # If we still don't have meaningful results, add industry context
            if not merged or all(len(it.get("snippet", "")) < 30 for it in merged):
                print(f"🔄 Adding industry context for: {query}")
                # Extract company name from query for industry context
                company_name = query.split()[0] if query else "Company"
                industry_context = self._get_industry_news_context(company_name)
                for ctx in industry_context:
                    key = (ctx.get("title"), ctx.get("snippet"))
                    if key not in seen:
                        seen.add(key)
                        merged.append(ctx)

            return merged
        return items

    def _validate_google_api_config(self) -> Dict:
        """Validate Google API configuration and provide recommendations"""
        issues = []
        recommendations = []

        if not self.google_api_key:
            issues.append("Google API key not configured")
            recommendations.append("Set GOOGLE_API_KEY environment variable")
        else:
            print(f"✅ Google API key configured: {self.google_api_key[:10]}...")

        if not self.google_cse_id:
            issues.append("Google CSE ID not configured")
            recommendations.append("Set GOOGLE_CSE_ID environment variable")
        else:
            print(f"✅ Google CSE ID configured: {self.google_cse_id[:8]}...")

        # Test API access if both are configured
        if self.google_api_key and self.google_cse_id:
            try:
                test_url = "https://www.googleapis.com/customsearch/v1"
                test_params = {
                    "key": self.google_api_key,
                    "cx": self.google_cse_id,
                    "q": "test",
                    "num": 1,
                }

                response = requests.get(test_url, params=test_params, timeout=5)

                if response.status_code == 200:
                    print("✅ Google API test successful")
                elif response.status_code == 403:
                    issues.append("Google API 403 Forbidden - Check API key and CSE ID")
                    recommendations.append("Verify Google API key is valid")
                    recommendations.append("Verify Custom Search Engine ID is correct")
                    recommendations.append("Check API quotas and billing")
                elif response.status_code == 429:
                    issues.append("Google API 429 Rate Limited")
                    recommendations.append("Wait before making more requests")
                    recommendations.append("Consider upgrading API quota")
                else:
                    issues.append(f"Google API test failed: {response.status_code}")
                    recommendations.append("Check API configuration")

            except Exception as e:
                issues.append(f"Google API test error: {e}")
                recommendations.append("Check network connectivity")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "recommendations": recommendations,
        }

    def _gather_guest_info(
        self,
        guest_name: str,
        website: str = None,
        additional_info: str = None,
        web_results: List[Dict] = None,
    ) -> str:
        """Gather basic information about the guest including web search results"""
        info_parts = [f"Guest Name: {guest_name}"]

        if website:
            info_parts.append(f"Website: {website}")
            # Try to extract domain for context
            try:
                domain = urlparse(website).netloc
                if domain:
                    info_parts.append(f"Domain: {domain}")
            except:
                pass

        if additional_info:
            info_parts.append(f"Additional Info: {additional_info}")

        # Add web search results
        if web_results:
            info_parts.append("\nWeb Search Results:")
            for i, result in enumerate(web_results[:3], 1):  # Limit to top 3 results
                info_parts.append(f"\nResult {i}:")
                info_parts.append(f"Title: {result.get('title', 'N/A')}")
                info_parts.append(f"Snippet: {result.get('snippet', 'N/A')}")
                info_parts.append(f"Link: {result.get('link', 'N/A')}")

        return "\n".join(info_parts)

    def _create_research_prompt(self, guest_name: str, guest_info: str) -> str:
        """Create a detailed prompt for guest research"""
        return f"""
Research this podcast guest and provide comprehensive information for the host:

GUEST INFORMATION:
{guest_info}

Please provide research in the following JSON format:
{{
    "profile": "A brief professional profile and background summary",
    "talking_points": [
        "Key topic or achievement 1",
        "Key topic or achievement 2", 
        "Key topic or achievement 3",
        "Key topic or achievement 4",
        "Key topic or achievement 5"
    ],
    "questions": [
        "Engaging question about their background or expertise 1",
        "Engaging question about their background or expertise 2",
        "Engaging question about their background or expertise 3",
        "Engaging question about their background or expertise 4",
        "Engaging question about their background or expertise 5"
    ],
    "recent_work": "Any recent projects, publications, or notable work",
    "controversies": "Any known controversies or sensitive topics to avoid",
    "interests": "Personal interests or hobbies that could be conversation starters"
}}

Focus on creating engaging, relevant talking points and questions that would make for an interesting podcast conversation.
"""

    def _parse_research_response(self, response_text: str, guest_name: str) -> Dict:
        """Parse the AI response into structured research"""
        try:
            # Try to extract JSON from response
            if "{" in response_text and "}" in response_text:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_str = response_text[start:end]
                research = json.loads(json_str)

                # Ensure all required fields exist
                required_fields = ["profile", "talking_points", "questions"]
                for field in required_fields:
                    if field not in research:
                        research[field] = []

                return research
            else:
                return self._parse_text_response(response_text, guest_name)

        except json.JSONDecodeError:
            return self._parse_text_response(response_text, guest_name)

    def _parse_text_response(self, response_text: str, guest_name: str) -> Dict:
        """Parse text response when JSON parsing fails"""
        return {
            "profile": f"{guest_name} is a notable guest with expertise in their field.",
            "talking_points": [
                "Professional background and experience",
                "Current projects and interests",
                "Industry insights and trends",
            ],
            "questions": [
                "What inspired your career path?",
                "Can you tell us about your current projects?",
                "What advice would you give to someone starting out?",
                "What trends do you see in your industry?",
                "Can you share a memorable story from your journey?",
            ],
            "expertise_areas": ["Professional development", "Industry expertise"],
            "recent_achievements": ["Notable accomplishments"],
            "conversation_starters": ["Professional background", "Current interests"],
        }

    def _get_fallback_research(self, guest_name: str, website: str = None) -> Dict:
        """Provide basic research when API is not available"""
        profile = f"{guest_name} is a notable guest"
        if website:
            profile += f" from {website}"
        profile += " with expertise in their field."

        return {
            "profile": profile,
            "talking_points": [
                "Professional background and experience",
                "Current projects and interests",
                "Industry insights and trends",
                "Notable achievements or milestones",
                "Future goals and aspirations",
            ],
            "questions": [
                "What inspired your career path?",
                "Can you tell us about your current projects?",
                "What challenges have you faced in your field?",
                "What advice would you give to someone starting out?",
                "What trends do you see in your industry?",
                "Can you share a memorable story from your journey?",
                "What are your future goals or plans?",
                "How do you stay motivated and productive?",
            ],
            "expertise_areas": ["Professional development", "Industry expertise"],
            "recent_achievements": ["Notable accomplishments"],
            "conversation_starters": ["Professional background", "Current interests"],
        }

    def get_quick_research(self, guest_name: str) -> Dict:
        """Get basic research without website or additional info"""
        return self.research(guest_name)

    def get_detailed_research(
        self, guest_name: str, website: str, additional_info: str = None
    ) -> Dict:
        """Get comprehensive research with all available information"""
        return self.research(guest_name, website, additional_info)

    def search_web(self, query: str, website: str = None) -> List[Dict]:
        """
        Public method to search the web for any query

        Args:
            query: Search query
            website: Optional website to restrict search to

        Returns:
            List of search results
        """
        return self._search_web(query, website)


# Example usage
if __name__ == "__main__":
    gr = GuestResearch()
    result = gr.research(
        "Jane Doe", "https://janedoe.com", "AI researcher and podcast host"
    )
    print(json.dumps(result, indent=2))
