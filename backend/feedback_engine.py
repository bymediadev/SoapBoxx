# backend/feedback_engine.py
import json
import os
from typing import Dict, List, Optional

from error_tracker import ErrorCategory, ErrorSeverity, track_api_error

# Try to import OpenAI - handle version compatibility
try:
    import openai
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Warning: OpenAI package not available. Install with: pip install openai")


class FeedbackEngine:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
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
            print("Warning: No OpenAI API key provided. Feedback will be limited.")
            self.client = None
            self.use_new_api = False

    def analyze(self, transcript: str = None, audio: bytes = None) -> Dict:
        """
        Analyze transcript and provide feedback for podcast hosts

        Args:
            transcript: Text transcript to analyze
            audio: Audio data (not used in current implementation)

        Returns:
            Dictionary containing feedback analysis
        """
        if not transcript or not transcript.strip():
            return {
                "listener_feedback": "No transcript provided for analysis.",
                "coaching_suggestions": ["Provide a transcript to get feedback."],
                "benchmark": "No data available",
                "confidence": 0.0,
            }

        if not self.api_key or not OPENAI_AVAILABLE:
            return self._get_fallback_feedback(transcript)

        try:
            # Create analysis prompt
            prompt = self._create_analysis_prompt(transcript)

            # Call OpenAI API using appropriate method
            if self.use_new_api and self.client:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert podcast coach and communication specialist.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=500,
                    temperature=0.7,
                )
                analysis_text = response.choices[0].message.content.strip()
            else:
                # Fallback to old API (only if new API is not available)
                try:
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an expert podcast coach and communication specialist.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=500,
                        temperature=0.7,
                    )
                    analysis_text = response.choices[0].message.content.strip()
                except Exception as old_api_error:
                    print(f"Old API failed: {old_api_error}")
                    return self._get_fallback_feedback(transcript)

            return self._parse_analysis_response(analysis_text, transcript)

        except Exception as e:
            print(f"Feedback analysis error: {e}")
            track_api_error(
                f"Feedback analysis error: {e}",
                component="feedback_engine",
                exception=e,
            )
            return self._get_fallback_feedback(transcript)

    def _create_analysis_prompt(self, transcript: str) -> str:
        """Create a detailed prompt for analyzing podcast content"""
        return f"""
Analyze this podcast transcript and provide constructive feedback for the host:

TRANSCRIPT:
{transcript}

Please provide analysis in the following JSON format:
{{
    "listener_feedback": "Brief assessment of how engaging and clear the content is",
    "coaching_suggestions": ["Specific suggestion 1", "Specific suggestion 2", "Specific suggestion 3"],
    "benchmark": "How this compares to professional podcast standards",
    "confidence": 0.85,
    "key_strengths": ["Strength 1", "Strength 2"],
    "areas_for_improvement": ["Area 1", "Area 2"]
}}

Focus on:
- Clarity and articulation
- Engagement and energy
- Structure and flow
- Audience connection
- Professional delivery
"""

    def _parse_analysis_response(self, response_text: str, transcript: str) -> Dict:
        """Parse the AI response into structured feedback"""
        try:
            # Try to extract JSON from response
            if "{" in response_text and "}" in response_text:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_str = response_text[start:end]
                analysis = json.loads(json_str)

                # Ensure all required fields exist
                required_fields = [
                    "listener_feedback",
                    "coaching_suggestions",
                    "benchmark",
                ]
                for field in required_fields:
                    if field not in analysis:
                        analysis[field] = "Analysis incomplete"

                return analysis
            else:
                # Fallback parsing
                return self._parse_text_response(response_text)

        except json.JSONDecodeError:
            return self._parse_text_response(response_text)

    def _parse_text_response(self, response_text: str) -> Dict:
        """Parse text response when JSON parsing fails"""
        return {
            "listener_feedback": (
                response_text[:200] + "..."
                if len(response_text) > 200
                else response_text
            ),
            "coaching_suggestions": [
                "Review the transcript for clarity",
                "Practice pacing and tone",
            ],
            "benchmark": "Analysis provided by AI",
            "confidence": 0.6,
        }

    def _get_fallback_feedback(self, transcript: str) -> Dict:
        """Provide basic feedback when API is not available"""
        word_count = len(transcript.split())

        if word_count < 50:
            return {
                "listener_feedback": "Very brief content. Consider expanding your points.",
                "coaching_suggestions": [
                    "Add more detail to your explanations",
                    "Include examples or stories",
                ],
                "benchmark": "Below average for content length",
                "confidence": 0.3,
            }
        elif word_count < 200:
            return {
                "listener_feedback": "Moderate content length. Good for concise communication.",
                "coaching_suggestions": [
                    "Vary your tone and pace",
                    "Include more engaging elements",
                ],
                "benchmark": "Average for brief segments",
                "confidence": 0.5,
            }
        else:
            return {
                "listener_feedback": "Substantial content. Good for detailed discussions.",
                "coaching_suggestions": [
                    "Break up long segments",
                    "Add transitions between topics",
                ],
                "benchmark": "Above average for content depth",
                "confidence": 0.7,
            }

    def get_specific_feedback(self, transcript: str, focus_area: str) -> Dict:
        """
        Get feedback focused on a specific area

        Args:
            transcript: Text to analyze
            focus_area: "clarity", "engagement", "structure", "energy"
        """
        focus_prompts = {
            "clarity": "Focus on how clear and understandable the speech is",
            "engagement": "Focus on how engaging and interesting the content is",
            "structure": "Focus on the organization and flow of ideas",
            "energy": "Focus on vocal energy and enthusiasm",
        }

        if focus_area not in focus_prompts:
            focus_area = "clarity"

        # Modify the analysis to focus on specific area
        return self.analyze(transcript)


# Example usage
if __name__ == "__main__":
    fe = FeedbackEngine()
    sample_transcript = "Hello, welcome to the show! Today we're talking about AI and its impact on podcasting."
    result = fe.analyze(transcript=sample_transcript)
    print(json.dumps(result, indent=2))
