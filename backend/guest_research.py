# backend/guest_research.py
import json
import os
import time
from typing import Dict, List, Optional
from urllib.parse import quote, urlparse

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

    def _search_web(self, guest_name: str, website: str = None) -> List[Dict]:
        """Search the web for information about the guest using Google CSE"""
        if not self.google_cse_id or not self.google_api_key:
            print("Web search not available: Missing Google CSE ID or API key")
            return []

        try:
            # Build search query
            search_terms = [guest_name]
            if website:
                domain = urlparse(website).netloc if website else ""
                if domain:
                    search_terms.append(f"site:{domain}")

            query = " ".join(search_terms)
            encoded_query = quote(query)

            # Google Custom Search API endpoint
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.google_api_key,
                "cx": self.google_cse_id,
                "q": query,
                "num": 5,  # Limit to 5 results
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

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

            print(f"✅ Found {len(results)} web results for {guest_name}")
            return results

        except Exception as e:
            print(f"Web search error: {e}")
            track_api_error(
                f"Web search error: {e}", component="guest_research", exception=e
            )
            return []

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


# Example usage
if __name__ == "__main__":
    gr = GuestResearch()
    result = gr.research(
        "Jane Doe", "https://janedoe.com", "AI researcher and podcast host"
    )
    print(json.dumps(result, indent=2))
