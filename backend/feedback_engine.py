# backend/feedback_engine.py
import json
import os
import time
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

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


@dataclass
class ContentMetrics:
    """Quantitative metrics for content analysis"""
    word_count: int
    sentence_count: int
    avg_sentence_length: float
    unique_words: int
    vocabulary_diversity: float  # Type-token ratio
    reading_level: str
    speaking_pace: float  # words per minute estimate
    topic_coherence: float  # 0-1 score
    engagement_signals: int  # questions, exclamations, etc.


@dataclass
class FeedbackScore:
    """Detailed scoring for different aspects"""
    clarity: float  # 0-100
    engagement: float  # 0-100
    structure: float  # 0-100
    energy: float  # 0-100
    professionalism: float  # 0-100
    overall: float  # 0-100


class FeedbackEngine:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
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
            print("Warning: No OpenAI API key provided. Feedback will be limited.")
            self.client = None
            self.use_new_api = False
        
        # Initialize analysis cache
        self.analysis_cache = {}
        self.cache_ttl = 3600  # 1 hour

    def analyze(self, transcript: str = None, audio: bytes = None, 
                analysis_depth: str = "comprehensive") -> Dict:
        """
        Analyze transcript and provide precise feedback for podcast hosts

        Args:
            transcript: Text transcript to analyze
            audio: Audio data (not used in current implementation)
            analysis_depth: "basic", "standard", "comprehensive", "expert"

        Returns:
            Dictionary containing detailed feedback analysis
        """
        if not transcript or not transcript.strip():
            return {
                "listener_feedback": "No transcript provided for analysis.",
                "coaching_suggestions": ["Provide a transcript to get feedback."],
                "benchmark": "No data available",
                "confidence": 0.0,
                "metrics": None,
                "scores": None,
                "detailed_analysis": None,
            }

        # Check cache first
        cache_key = f"{hash(transcript)}_{analysis_depth}"
        if cache_key in self.analysis_cache:
            cached_result = self.analysis_cache[cache_key]
            if time.time() - cached_result.get("timestamp", 0) < self.cache_ttl:
                return cached_result["result"]

        if not self.api_key or not OPENAI_AVAILABLE:
            result = self._get_enhanced_fallback_feedback(transcript, analysis_depth)
        else:
            try:
                result = self._perform_ai_analysis(transcript, analysis_depth)
            except Exception as e:
                print(f"Feedback analysis error: {e}")
                track_api_error(
                    f"Feedback analysis error: {e}",
                    component="feedback_engine",
                    exception=e,
                )
                result = self._get_enhanced_fallback_feedback(transcript, analysis_depth)

        # Cache the result
        self.analysis_cache[cache_key] = {
            "result": result,
            "timestamp": time.time()
        }

        return result

    def _perform_ai_analysis(self, transcript: str, analysis_depth: str) -> Dict:
        """Perform AI-powered analysis with varying depth levels"""
        
        # Calculate quantitative metrics first
        metrics = self._calculate_content_metrics(transcript)
        
        # Create depth-specific prompts
        if analysis_depth == "basic":
            prompt = self._create_basic_analysis_prompt(transcript, metrics)
            max_tokens = 300
        elif analysis_depth == "standard":
            prompt = self._create_standard_analysis_prompt(transcript, metrics)
            max_tokens = 500
        elif analysis_depth == "comprehensive":
            prompt = self._create_comprehensive_analysis_prompt(transcript, metrics)
            max_tokens = 800
        else:  # expert
            prompt = self._create_expert_analysis_prompt(transcript, metrics)
            max_tokens = 1200

        # Call OpenAI API
        if self.use_new_api and self.client:
            response = self.client.chat.completions.create(
                model="gpt-4" if analysis_depth in ["comprehensive", "expert"] else "gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(analysis_depth),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.3 if analysis_depth in ["comprehensive", "expert"] else 0.7,
            )
            analysis_text = response.choices[0].message.content.strip()
        else:
            # Fallback to old API
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": self._get_system_prompt(analysis_depth),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.3 if analysis_depth in ["comprehensive", "expert"] else 0.7,
                )
                analysis_text = response.choices[0].message.content.strip()
            except Exception as old_api_error:
                print(f"Old API failed: {old_api_error}")
                raise

        # Parse and enhance the response
        parsed_response = self._parse_enhanced_analysis_response(analysis_text, transcript, metrics)
        
        # Add quantitative scores
        parsed_response["metrics"] = metrics.__dict__
        parsed_response["scores"] = self._calculate_quantitative_scores(transcript, metrics)
        
        return parsed_response

    def _get_system_prompt(self, analysis_depth: str) -> str:
        """Get system prompt based on analysis depth"""
        base_prompt = "You are an expert podcast coach and communication specialist with deep knowledge of audio content analysis."
        
        if analysis_depth == "basic":
            return base_prompt + " Provide concise, actionable feedback."
        elif analysis_depth == "standard":
            return base_prompt + " Provide balanced feedback with specific examples."
        elif analysis_depth == "comprehensive":
            return base_prompt + " Provide detailed analysis with multiple improvement strategies."
        else:  # expert
            return base_prompt + " Provide expert-level analysis with industry benchmarks and advanced techniques."

    def _create_basic_analysis_prompt(self, transcript: str, metrics: ContentMetrics) -> str:
        """Create basic analysis prompt"""
        return f"""
Analyze this podcast transcript and provide basic feedback:

TRANSCRIPT:
{transcript}

BASIC METRICS:
- Word count: {metrics.word_count}
- Sentences: {metrics.sentence_count}
- Average sentence length: {metrics.avg_sentence_length:.1f} words

Provide feedback in this JSON format:
{{
    "listener_feedback": "Brief assessment",
    "coaching_suggestions": ["Suggestion 1", "Suggestion 2"],
    "benchmark": "Basic comparison",
    "confidence": 0.8
}}
"""

    def _create_standard_analysis_prompt(self, transcript: str, metrics: ContentMetrics) -> str:
        """Create standard analysis prompt"""
        return f"""
Analyze this podcast transcript and provide standard feedback:

TRANSCRIPT:
{transcript}

METRICS:
- Word count: {metrics.word_count}
- Sentences: {metrics.sentence_count}
- Average sentence length: {metrics.avg_sentence_length:.1f} words
- Vocabulary diversity: {metrics.vocabulary_diversity:.2f}
- Speaking pace: {metrics.speaking_pace:.1f} words/minute

Provide feedback in this JSON format:
{{
    "listener_feedback": "Assessment with examples",
    "coaching_suggestions": ["Specific suggestion 1", "Specific suggestion 2", "Specific suggestion 3"],
    "benchmark": "Industry comparison",
    "confidence": 0.85,
    "key_strengths": ["Strength 1", "Strength 2"],
    "areas_for_improvement": ["Area 1", "Area 2"]
}}
"""

    def _create_comprehensive_analysis_prompt(self, transcript: str, metrics: ContentMetrics) -> str:
        """Create comprehensive analysis prompt"""
        return f"""
Analyze this podcast transcript comprehensively:

TRANSCRIPT:
{transcript}

DETAILED METRICS:
- Word count: {metrics.word_count}
- Sentences: {metrics.sentence_count}
- Average sentence length: {metrics.avg_sentence_length:.1f} words
- Vocabulary diversity: {metrics.vocabulary_diversity:.2f}
- Reading level: {metrics.reading_level}
- Speaking pace: {metrics.speaking_pace:.1f} words/minute
- Topic coherence: {metrics.topic_coherence:.2f}
- Engagement signals: {metrics.engagement_signals}

Provide comprehensive feedback in this JSON format:
{{
    "listener_feedback": "Detailed assessment with specific examples",
    "coaching_suggestions": ["Detailed suggestion 1", "Detailed suggestion 2", "Detailed suggestion 3", "Detailed suggestion 4"],
    "benchmark": "Detailed industry comparison with specific standards",
    "confidence": 0.9,
    "key_strengths": ["Specific strength 1", "Specific strength 2", "Specific strength 3"],
    "areas_for_improvement": ["Specific area 1", "Specific area 2", "Specific area 3"],
    "content_structure_analysis": "Analysis of how well the content is organized",
    "audience_engagement_tactics": "Specific tactics to improve engagement",
    "professional_development_path": "Next steps for improvement"
}}
"""

    def _create_expert_analysis_prompt(self, transcript: str, metrics: ContentMetrics) -> str:
        """Create expert-level analysis prompt"""
        return f"""
Provide expert-level podcast content analysis:

TRANSCRIPT:
{transcript}

COMPREHENSIVE METRICS:
- Word count: {metrics.word_count}
- Sentences: {metrics.sentence_count}
- Average sentence length: {metrics.avg_sentence_length:.1f} words
- Vocabulary diversity: {metrics.vocabulary_diversity:.2f}
- Reading level: {metrics.reading_level}
- Speaking pace: {metrics.speaking_pace:.1f} words/minute
- Topic coherence: {metrics.topic_coherence:.2f}
- Engagement signals: {metrics.engagement_signals}

Provide expert analysis in this JSON format:
{{
    "listener_feedback": "Expert-level assessment with industry context",
    "coaching_suggestions": ["Expert suggestion 1", "Expert suggestion 2", "Expert suggestion 3", "Expert suggestion 4", "Expert suggestion 5"],
    "benchmark": "Industry-leading standards comparison",
    "confidence": 0.95,
    "key_strengths": ["Expert-identified strength 1", "Expert-identified strength 2", "Expert-identified strength 3", "Expert-identified strength 4"],
    "areas_for_improvement": ["Expert-identified area 1", "Expert-identified area 2", "Expert-identified area 3", "Expert-identified area 4"],
    "content_structure_analysis": "Advanced structural analysis with flow optimization",
    "audience_engagement_tactics": "Advanced engagement strategies with psychological insights",
    "professional_development_path": "Comprehensive improvement roadmap",
    "industry_benchmarks": "Comparison with top podcasters in the field",
    "advanced_techniques": "Cutting-edge podcasting techniques to consider",
    "content_strategy_recommendations": "Strategic content planning advice"
}}
"""

    def _calculate_content_metrics(self, transcript: str) -> ContentMetrics:
        """Calculate quantitative content metrics"""
        words = transcript.split()
        sentences = re.split(r'[.!?]+', transcript)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        word_count = len(words)
        sentence_count = len(sentences)
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
        
        unique_words = len(set(word.lower() for word in words))
        vocabulary_diversity = unique_words / word_count if word_count > 0 else 0
        
        # Estimate reading level (simplified Flesch-Kincaid)
        if sentence_count > 0 and word_count > 0:
            syllables = sum(self._count_syllables(word) for word in words)
            flesch_score = 206.835 - (1.015 * (word_count / sentence_count)) - (84.6 * (syllables / word_count))
            if flesch_score >= 90:
                reading_level = "Very Easy"
            elif flesch_score >= 80:
                reading_level = "Easy"
            elif flesch_score >= 70:
                reading_level = "Fairly Easy"
            elif flesch_score >= 60:
                reading_level = "Standard"
            elif flesch_score >= 50:
                reading_level = "Fairly Difficult"
            elif flesch_score >= 30:
                reading_level = "Difficult"
            else:
                reading_level = "Very Difficult"
        else:
            reading_level = "Unknown"
        
        # Estimate speaking pace (words per minute)
        speaking_pace = word_count / 2.5  # Rough estimate: 2.5 minutes for typical content
        
        # Calculate topic coherence (simplified)
        topic_coherence = self._calculate_topic_coherence(transcript)
        
        # Count engagement signals
        engagement_signals = len(re.findall(r'[!?]', transcript))
        
        return ContentMetrics(
            word_count=word_count,
            sentence_count=sentence_count,
            avg_sentence_length=avg_sentence_length,
            unique_words=unique_words,
            vocabulary_diversity=vocabulary_diversity,
            reading_level=reading_level,
            speaking_pace=speaking_pace,
            topic_coherence=topic_coherence,
            engagement_signals=engagement_signals
        )

    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word (simplified)"""
        word = word.lower()
        count = 0
        vowels = "aeiouy"
        on_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not on_vowel:
                count += 1
            on_vowel = is_vowel
        
        if word.endswith('e'):
            count -= 1
        if count == 0:
            count = 1
        return count

    def _calculate_topic_coherence(self, transcript: str) -> float:
        """Calculate topic coherence score (0-1)"""
        # Simple implementation: check for topic-related words appearing multiple times
        words = transcript.lower().split()
        word_freq = {}
        for word in words:
            if len(word) > 3:  # Only consider meaningful words
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Calculate coherence based on word repetition
        total_words = len(words)
        repeated_words = sum(1 for freq in word_freq.values() if freq > 1)
        
        if total_words == 0:
            return 0.0
        
        coherence = min(1.0, (repeated_words / total_words) * 5)  # Scale factor
        return round(coherence, 2)

    def _calculate_quantitative_scores(self, transcript: str, metrics: ContentMetrics) -> FeedbackScore:
        """Calculate quantitative scores for different aspects"""
        
        # Clarity score (based on sentence length, vocabulary diversity)
        clarity = 100 - min(100, (metrics.avg_sentence_length - 15) * 2)
        clarity = max(0, min(100, clarity))
        
        # Engagement score (based on engagement signals, vocabulary diversity)
        engagement = min(100, metrics.engagement_signals * 10 + metrics.vocabulary_diversity * 50)
        
        # Structure score (based on topic coherence, sentence count)
        structure = min(100, metrics.topic_coherence * 100 + (metrics.sentence_count / 10))
        
        # Energy score (based on engagement signals, speaking pace)
        energy = min(100, metrics.engagement_signals * 15 + (metrics.speaking_pace / 2))
        
        # Professionalism score (based on reading level, vocabulary diversity)
        if metrics.reading_level in ["Standard", "Fairly Easy", "Easy"]:
            professionalism = 80 + metrics.vocabulary_diversity * 20
        else:
            professionalism = 60 + metrics.vocabulary_diversity * 20
        professionalism = max(0, min(100, professionalism))
        
        # Overall score (weighted average)
        overall = (clarity * 0.25 + engagement * 0.25 + structure * 0.2 + 
                  energy * 0.15 + professionalism * 0.15)
        
        return FeedbackScore(
            clarity=round(clarity, 1),
            engagement=round(engagement, 1),
            structure=round(structure, 1),
            energy=round(energy, 1),
            professionalism=round(professionalism, 1),
            overall=round(overall, 1)
        )

    def _parse_enhanced_analysis_response(self, response_text: str, transcript: str, 
                                        metrics: ContentMetrics) -> Dict:
        """Parse the AI response into structured feedback with enhanced parsing"""
        try:
            # Try to extract JSON from response
            if "{" in response_text and "}" in response_text:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_str = response_text[start:end]
                analysis = json.loads(json_str)

                # Ensure all required fields exist with defaults
                required_fields = {
                    "listener_feedback": "Analysis incomplete",
                    "coaching_suggestions": ["Review the transcript for improvement opportunities"],
                    "benchmark": "Standard analysis provided",
                    "confidence": 0.7,
                    "key_strengths": ["Content analysis completed"],
                    "areas_for_improvement": ["General improvement areas identified"]
                }
                
                for field, default in required_fields.items():
                    if field not in analysis:
                        analysis[field] = default

                # Add timestamp and metadata
                analysis["analysis_timestamp"] = datetime.now().isoformat()
                analysis["analysis_version"] = "2.0"
                analysis["transcript_length"] = len(transcript)
                
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
                "Review the transcript for clarity improvements",
                "Practice pacing and tone variation",
                "Consider adding more engaging elements"
            ],
            "benchmark": "AI analysis provided",
            "confidence": 0.6,
            "key_strengths": ["Content analysis completed"],
            "areas_for_improvement": ["General improvement areas identified"],
            "analysis_timestamp": datetime.now().isoformat(),
            "analysis_version": "2.0"
        }

    def _get_enhanced_fallback_feedback(self, transcript: str, analysis_depth: str) -> Dict:
        """Provide enhanced fallback feedback when API is not available"""
        metrics = self._calculate_content_metrics(transcript)
        scores = self._calculate_quantitative_scores(transcript, metrics)
        
        # Enhanced word-count based feedback
        if metrics.word_count < 50:
            feedback = {
                "listener_feedback": "Very brief content. Consider expanding your points with examples and details.",
                "coaching_suggestions": [
                    "Add more detail to your explanations",
                    "Include specific examples or stories",
                    "Expand on key points with supporting information"
                ],
                "benchmark": "Below average for content depth - aim for 100+ words for meaningful analysis",
                "confidence": 0.8,
                "key_strengths": ["Concise communication"],
                "areas_for_improvement": ["Content depth", "Detail level", "Example inclusion"]
            }
        elif metrics.word_count < 200:
            feedback = {
                "listener_feedback": "Moderate content length. Good foundation for concise communication.",
                "coaching_suggestions": [
                    "Vary your tone and pace throughout",
                    "Include more engaging elements like questions",
                    "Add transitions between topics"
                ],
                "benchmark": "Average for brief segments - good for focused topics",
                "confidence": 0.7,
                "key_strengths": ["Focused content", "Moderate depth"],
                "areas_for_improvement": ["Pacing variation", "Engagement elements", "Topic transitions"]
            }
        else:
            feedback = {
                "listener_feedback": "Substantial content. Good for detailed discussions and comprehensive coverage.",
                "coaching_suggestions": [
                    "Break up long segments with natural pauses",
                    "Add clear transitions between topics",
                    "Include audience engagement checkpoints"
                ],
                "benchmark": "Above average for content depth - excellent for comprehensive topics",
                "confidence": 0.8,
                "key_strengths": ["Comprehensive coverage", "Detailed explanations"],
                "areas_for_improvement": ["Segment management", "Transition clarity", "Audience interaction"]
            }
        
        # Add metrics and scores
        feedback["metrics"] = metrics.__dict__
        feedback["scores"] = scores.__dict__
        feedback["analysis_timestamp"] = datetime.now().isoformat()
        feedback["analysis_version"] = "2.0"
        feedback["analysis_depth"] = analysis_depth
        
        return feedback

    def get_specific_feedback(self, transcript: str, focus_area: str, 
                            analysis_depth: str = "standard") -> Dict:
        """
        Get feedback focused on a specific area with enhanced precision

        Args:
            transcript: Text to analyze
            focus_area: "clarity", "engagement", "structure", "energy", "professionalism"
            analysis_depth: Analysis depth level
        """
        focus_prompts = {
            "clarity": "Focus on how clear and understandable the speech is, including articulation, vocabulary choice, and explanation quality",
            "engagement": "Focus on how engaging and interesting the content is, including audience connection, storytelling, and interactive elements",
            "structure": "Focus on the organization and flow of ideas, including logical progression, transitions, and content architecture",
            "energy": "Focus on vocal energy and enthusiasm, including pacing, tone variation, and dynamic delivery",
            "professionalism": "Focus on professional delivery standards, including industry terminology, credibility markers, and presentation quality"
        }

        if focus_area not in focus_prompts:
            focus_area = "clarity"

        # Get comprehensive analysis first
        full_analysis = self.analyze(transcript, analysis_depth=analysis_depth)
        
        # Enhance with focus-specific insights
        focus_analysis = {
            **full_analysis,
            "focus_area": focus_area,
            "focus_specific_suggestions": self._get_focus_specific_suggestions(
                focus_area, full_analysis, full_analysis.get("metrics", {})
            )
        }
        
        return focus_analysis

    def _get_focus_specific_suggestions(self, focus_area: str, analysis: Dict, 
                                      metrics: Dict) -> List[str]:
        """Get suggestions specific to the focus area"""
        suggestions = []
        
        if focus_area == "clarity":
            if metrics.get("avg_sentence_length", 0) > 20:
                suggestions.append("Break down long sentences into shorter, clearer statements")
            if metrics.get("vocabulary_diversity", 0) < 0.3:
                suggestions.append("Vary your vocabulary to avoid repetition and improve clarity")
            suggestions.append("Use concrete examples to illustrate abstract concepts")
            
        elif focus_area == "engagement":
            if metrics.get("engagement_signals", 0) < 2:
                suggestions.append("Add more questions and exclamations to engage listeners")
            suggestions.append("Include personal stories or anecdotes to connect with audience")
            suggestions.append("Vary your tone and pace to maintain listener interest")
            
        elif focus_area == "structure":
            if metrics.get("topic_coherence", 0) < 0.5:
                suggestions.append("Organize content with clear topic transitions")
            suggestions.append("Use signposting language to guide listeners through your content")
            suggestions.append("Create logical flow from introduction to conclusion")
            
        elif focus_area == "energy":
            if metrics.get("speaking_pace", 0) < 120:
                suggestions.append("Increase your speaking pace to maintain energy")
            suggestions.append("Vary your vocal pitch and volume for dynamic delivery")
            suggestions.append("Use pauses strategically to emphasize key points")
            
        elif focus_area == "professionalism":
            if metrics.get("reading_level", "") in ["Very Easy", "Easy"]:
                suggestions.append("Incorporate industry-specific terminology for credibility")
            suggestions.append("Maintain consistent professional tone throughout")
            suggestions.append("Use data and research to support your points")
        
        return suggestions

    def get_comparative_analysis(self, transcript1: str, transcript2: str) -> Dict:
        """
        Compare two transcripts and provide comparative feedback
        """
        analysis1 = self.analyze(transcript1, analysis_depth="comprehensive")
        analysis2 = self.analyze(transcript2, analysis_depth="comprehensive")
        
        # Calculate improvement metrics
        scores1 = analysis1.get("scores", {})
        scores2 = analysis2.get("scores", {})
        
        improvements = {}
        for key in ["clarity", "engagement", "structure", "energy", "professionalism", "overall"]:
            if key in scores1 and key in scores2:
                improvement = scores2[key] - scores1[key]
                improvements[key] = {
                    "before": scores1[key],
                    "after": scores2[key],
                    "improvement": improvement,
                    "percentage_change": (improvement / scores1[key] * 100) if scores1[key] > 0 else 0
                }
        
        return {
            "transcript_1_analysis": analysis1,
            "transcript_2_analysis": analysis2,
            "improvement_analysis": improvements,
            "comparison_timestamp": datetime.now().isoformat(),
            "summary": self._generate_comparison_summary(improvements)
        }

    def _generate_comparison_summary(self, improvements: Dict) -> str:
        """Generate a summary of improvements between two transcripts"""
        overall_improvement = improvements.get("overall", {}).get("improvement", 0)
        
        if overall_improvement > 10:
            return "Significant improvement across all areas"
        elif overall_improvement > 5:
            return "Notable improvement with room for continued growth"
        elif overall_improvement > 0:
            return "Slight improvement, focus on specific areas for better results"
        elif overall_improvement > -5:
            return "Similar performance, consider different approaches"
        else:
            return "Performance declined, review recent changes and strategies"

    def clear_cache(self):
        """Clear the analysis cache"""
        self.analysis_cache.clear()

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "cache_size": len(self.analysis_cache),
            "cache_ttl": self.cache_ttl,
            "oldest_entry": min([entry["timestamp"] for entry in self.analysis_cache.values()]) if self.analysis_cache else None,
            "newest_entry": max([entry["timestamp"] for entry in self.analysis_cache.values()]) if self.analysis_cache else None
        }


# Example usage
if __name__ == "__main__":
    fe = FeedbackEngine()
    sample_transcript = "Hello, welcome to the show! Today we're talking about AI and its impact on podcasting. This is a fascinating topic that affects all of us in the content creation space."
    result = fe.analyze(transcript=sample_transcript, analysis_depth="comprehensive")
    print(json.dumps(result, indent=2))
