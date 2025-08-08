# backend/guest_research.py
import json
import os
import time
from typing import Dict, List, Optional
from urllib.parse import quote, urlparse
from datetime import datetime

import requests
from error_tracker import ErrorCategory, ErrorSeverity, track_api_error

# Try to import OpenAI - handle version compatibility
try:
    import openai
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Warning: OpenAI package not available. Install with: pip install openai")


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
                self.client = OpenAI(api_key=self.api_key)
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
                "social_media": []
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
                "results": []
            }

    def _search_company_info(self, company_name: str) -> Dict:
        """Search for general company information"""
        try:
            # Build search queries for company info
            queries = [
                f'"{company_name}" company',
                f'"{company_name}" about us',
                f'"{company_name}" official website',
                f'"{company_name}" headquarters location'
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
            
            return {
                "web_results": unique_results[:10],  # Limit to top 10 results
                "company_name": company_name,
                "search_queries": queries
            }
            
        except Exception as e:
            print(f"Company info search error: {e}")
            return {"web_results": [], "error": str(e)}

    def _search_linkedin(self, company_name: str) -> List[Dict]:
        """Search for LinkedIn profiles and company pages"""
        try:
            # Build LinkedIn-specific search queries
            linkedin_queries = [
                f'"{company_name}" site:linkedin.com',
                f'"{company_name}" CEO site:linkedin.com',
                f'"{company_name}" founder site:linkedin.com',
                f'"{company_name}" executive site:linkedin.com'
            ]
            
            linkedin_results = []
            for query in linkedin_queries:
                results = self._search_web(query)
                for result in results:
                    if "linkedin.com" in result.get("link", ""):
                        result["type"] = "linkedin_profile"
                        linkedin_results.append(result)
            
            return linkedin_results[:15]  # Limit to top 15 LinkedIn results
            
        except Exception as e:
            print(f"LinkedIn search error: {e}")
            return []

    def _search_executives(self, company_name: str) -> List[Dict]:
        """Search for executive profiles and leadership information"""
        try:
            # Build executive search queries
            executive_queries = [
                f'"{company_name}" CEO president founder',
                f'"{company_name}" executive team leadership',
                f'"{company_name}" board of directors',
                f'"{company_name}" management team'
            ]
            
            executive_results = []
            for query in executive_queries:
                results = self._search_web(query)
                for result in results:
                    result["type"] = "executive_info"
                    executive_results.append(result)
            
            return executive_results[:10]  # Limit to top 10 executive results
            
        except Exception as e:
            print(f"Executive search error: {e}")
            return []

    def _search_company_news(self, company_name: str) -> List[Dict]:
        """Search for recent company news and press releases"""
        try:
            # Build news search queries
            news_queries = [
                f'"{company_name}" news 2024',
                f'"{company_name}" press release',
                f'"{company_name}" announcement',
                f'"{company_name}" recent developments'
            ]
            
            news_results = []
            for query in news_queries:
                results = self._search_web(query)
                for result in results:
                    result["type"] = "news"
                    news_results.append(result)
            
            return news_results[:10]  # Limit to top 10 news results
            
        except Exception as e:
            print(f"Company news search error: {e}")
            return []

    def _generate_business_summary(self, company_name: str, search_results: Dict) -> str:
        """Generate an AI-powered summary of business search results"""
        try:
            # Prepare context for AI summary
            context_parts = [f"Company: {company_name}"]
            
            if search_results.get("company_info", {}).get("web_results"):
                context_parts.append("Company Information:")
                for result in search_results["company_info"]["web_results"][:3]:
                    context_parts.append(f"- {result.get('title', 'N/A')}: {result.get('snippet', 'N/A')}")
            
            if search_results.get("linkedin_profiles"):
                context_parts.append("LinkedIn Profiles:")
                for profile in search_results["linkedin_profiles"][:3]:
                    context_parts.append(f"- {profile.get('title', 'N/A')}: {profile.get('snippet', 'N/A')}")
            
            if search_results.get("news"):
                context_parts.append("Recent News:")
                for news in search_results["news"][:3]:
                    context_parts.append(f"- {news.get('title', 'N/A')}: {news.get('snippet', 'N/A')}")
            
            context = "\n".join(context_parts)
            
            # Create summary prompt
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
                            "content": "You are an expert business analyst and researcher.",
                        },
                        {"role": "user", "content": summary_prompt},
                    ],
                    max_tokens=500,
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
                            "content": "You are an expert business analyst and researcher.",
                        },
                        {"role": "user", "content": summary_prompt},
                    ],
                    max_tokens=500,
                    temperature=0.7,
                )
                summary = response.choices[0].message.content.strip()
            
            return summary
            
        except Exception as e:
            print(f"Business summary generation error: {e}")
            return f"Summary generation failed: {str(e)}"

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
                print(f"⚠️ Google API 403 Forbidden - API key may be invalid or quota exceeded")
                print(f"   Query: {final_query}")
                print(f"   CSE ID: {self.google_cse_id[:8]}...")
                print(f"   API Key: {self.google_api_key[:10]}..." if self.google_api_key else "   API Key: Not set")
                track_api_error(
                    f"Google API 403 Forbidden for query: {final_query}",
                    component="guest_research",
                    severity=ErrorSeverity.MEDIUM
                )
                return self._get_fallback_web_results(query)
                
            elif response.status_code == 429:
                print(f"⚠️ Google API 429 Rate Limited - Too many requests")
                track_api_error(
                    f"Google API 429 Rate Limited for query: {final_query}",
                    component="guest_research",
                    severity=ErrorSeverity.MEDIUM
                )
                return self._get_fallback_web_results(query)
                
            elif response.status_code != 200:
                print(f"⚠️ Google API Error {response.status_code}: {response.text}")
                track_api_error(
                    f"Google API Error {response.status_code}: {response.text}",
                    component="guest_research",
                    severity=ErrorSeverity.MEDIUM
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
                severity=ErrorSeverity.MEDIUM
            )
            return self._get_fallback_web_results(query)
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Web search request error: {e}")
            track_api_error(
                f"Web search request error: {e}",
                component="guest_research",
                severity=ErrorSeverity.MEDIUM
            )
            return self._get_fallback_web_results(query)
            
        except Exception as e:
            print(f"Web search error: {e}")
            track_api_error(
                f"Web search error: {e}", 
                component="guest_research", 
                exception=e
            )
            return self._get_fallback_web_results(query)

    def _get_fallback_web_results(self, query: str) -> List[Dict]:
        """Provide fallback results when web search fails"""
        print(f"🔄 Using fallback research for: {query}")
        
        # Return basic fallback results
        return [
            {
                "title": f"Research for {query}",
                "snippet": f"Basic information about {query} - web search unavailable",
                "link": "",
                "displayLink": "",
                "fallback": True
            }
        ]

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
                    "num": 1
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
            "recommendations": recommendations
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
