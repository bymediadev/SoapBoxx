#!/usr/bin/env python3
"""
Barebones Feedback Engine for SoapBoxx Demo
Provides local text analysis without external API dependencies
"""

import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ContentMetrics:
    """Content analysis metrics"""
    word_count: int
    sentence_count: int
    average_sentence_length: float
    unique_words: int
    reading_time_minutes: float
    speaking_pace_wpm: float
    topic_coherence_score: float
    engagement_indicators: List[str]


@dataclass
class FeedbackScore:
    """Feedback scoring for different areas"""
    clarity: float
    engagement: float
    structure: float
    energy: float
    professionalism: float
    overall_score: float


class BarebonesFeedbackEngine:
    """Simplified feedback engine with local analysis only"""
    
    def __init__(self):
        self.analysis_cache = {}
        self.cache_ttl = 3600  # 1 hour
        
    def analyze(self, transcript: str = None, audio: bytes = None,
                analysis_depth: str = "comprehensive") -> Dict:
        """
        Analyze transcript and provide local feedback
        """
        if not transcript:
            return self._get_fallback_feedback("No transcript provided")
        
        # Check cache first
        cache_key = f"{hash(transcript)}_{analysis_depth}"
        if cache_key in self.analysis_cache:
            cached = self.analysis_cache[cache_key]
            if time.time() - cached.get("timestamp", 0) < self.cache_ttl:
                return cached["result"]
        
        try:
            # Perform local analysis
            metrics = self._calculate_content_metrics(transcript)
            scores = self._calculate_local_scores(transcript, analysis_depth)
            feedback = self._generate_local_feedback(transcript, metrics, scores, analysis_depth)
            
            result = {
                "success": True,
                "analysis_depth": analysis_depth,
                "metrics": metrics,
                "scores": scores,
                "feedback": feedback,
                "timestamp": time.time(),
                "analysis_type": "local"
            }
            
            # Cache the result
            self.analysis_cache[cache_key] = {
                "result": result,
                "timestamp": time.time()
            }
            
            return result
            
        except Exception as e:
            return self._get_fallback_feedback(f"Analysis failed: {str(e)}")
    
    def _calculate_content_metrics(self, transcript: str) -> ContentMetrics:
        """Calculate basic content metrics"""
        words = transcript.split()
        sentences = re.split(r'[.!?]+', transcript)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        word_count = len(words)
        sentence_count = len(sentences)
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
        unique_words = len(set(word.lower() for word in words))
        
        # Estimate reading time (average 200 words per minute)
        reading_time = word_count / 200.0
        
        # Estimate speaking pace (average 150 words per minute)
        speaking_pace = 150
        
        # Simple topic coherence (based on repeated key phrases)
        key_phrases = self._extract_key_phrases(transcript)
        coherence_score = min(1.0, len(key_phrases) / 10.0)
        
        # Engagement indicators
        engagement_indicators = self._find_engagement_indicators(transcript)
        
        return ContentMetrics(
            word_count=word_count,
            sentence_count=sentence_count,
            average_sentence_length=round(avg_sentence_length, 2),
            unique_words=unique_words,
            reading_time_minutes=round(reading_time, 2),
            speaking_pace_wpm=speaking_pace,
            topic_coherence_score=round(coherence_score, 2),
            engagement_indicators=engagement_indicators
        )
    
    def _extract_key_phrases(self, transcript: str) -> List[str]:
        """Extract key phrases from transcript"""
        # Simple key phrase extraction
        words = transcript.lower().split()
        phrase_counts = {}
        
        # Look for 2-3 word phrases
        for i in range(len(words) - 1):
            phrase = " ".join(words[i:i+2])
            if len(phrase) > 5:  # Only meaningful phrases
                phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
        
        # Return top phrases
        sorted_phrases = sorted(phrase_counts.items(), key=lambda x: x[1], reverse=True)
        return [phrase for phrase, count in sorted_phrases[:5] if count > 1]
    
    def _find_engagement_indicators(self, transcript: str) -> List[str]:
        """Find engagement indicators in transcript"""
        indicators = []
        transcript_lower = transcript.lower()
        
        # Question marks
        if transcript.count('?') > 0:
            indicators.append("Contains questions")
        
        # Exclamation marks
        if transcript.count('!') > 0:
            indicators.append("Uses emphasis")
        
        # Personal pronouns
        personal_words = ['i', 'you', 'we', 'us', 'our', 'my', 'your']
        if any(word in transcript_lower for word in personal_words):
            indicators.append("Uses personal language")
        
        # Storytelling words
        story_words = ['because', 'when', 'then', 'after', 'before', 'while']
        if any(word in transcript_lower for word in story_words):
            indicators.append("Uses storytelling elements")
        
        return indicators[:3]  # Limit to top 3
    
    def _calculate_local_scores(self, transcript: str, analysis_depth: str) -> FeedbackScore:
        """Calculate local feedback scores"""
        # Base scores based on content analysis
        clarity = self._score_clarity(transcript)
        engagement = self._score_engagement(transcript)
        structure = self._score_structure(transcript)
        energy = self._score_energy(transcript)
        professionalism = self._score_professionalism(transcript)
        
        # Overall score (weighted average)
        weights = [0.25, 0.25, 0.2, 0.15, 0.15]
        overall = (clarity * weights[0] + engagement * weights[1] + 
                  structure * weights[2] + energy * weights[3] + 
                  professionalism * weights[4])
        
        return FeedbackScore(
            clarity=round(clarity, 2),
            engagement=round(engagement, 2),
            structure=round(structure, 2),
            energy=round(energy, 2),
            professionalism=round(professionalism, 2),
            overall_score=round(overall, 2)
        )
    
    def _score_clarity(self, transcript: str) -> float:
        """Score clarity based on text analysis"""
        words = transcript.split()
        sentences = re.split(r'[.!?]+', transcript)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not words or not sentences:
            return 5.0
        
        # Shorter sentences = clearer (up to a point)
        avg_sentence_length = len(words) / len(sentences)
        if avg_sentence_length <= 15:
            clarity_score = 9.0
        elif avg_sentence_length <= 25:
            clarity_score = 7.0
        elif avg_sentence_length <= 35:
            clarity_score = 5.0
        else:
            clarity_score = 3.0
        
        # Bonus for good punctuation
        if transcript.count(',') > 0:
            clarity_score += 0.5
        
        return min(10.0, clarity_score)
    
    def _score_engagement(self, transcript: str) -> float:
        """Score engagement based on text analysis"""
        engagement_score = 5.0  # Base score
        
        # Questions increase engagement
        engagement_score += min(2.0, transcript.count('?') * 0.5)
        
        # Exclamations increase engagement
        engagement_score += min(1.5, transcript.count('!') * 0.3)
        
        # Personal language increases engagement
        personal_words = ['i', 'you', 'we', 'us', 'our', 'my', 'your']
        personal_count = sum(1 for word in transcript.lower().split() if word in personal_words)
        engagement_score += min(1.5, personal_count * 0.1)
        
        return min(10.0, engagement_score)
    
    def _score_structure(self, transcript: str) -> float:
        """Score structure based on text analysis"""
        structure_score = 5.0  # Base score
        
        # Paragraphs indicate structure
        paragraphs = transcript.split('\n\n')
        if len(paragraphs) > 1:
            structure_score += 2.0
        
        # Transition words indicate structure
        transition_words = ['first', 'second', 'third', 'finally', 'however', 'therefore', 'meanwhile']
        transition_count = sum(1 for word in transcript.lower().split() if word in transition_words)
        structure_score += min(2.0, transition_count * 0.5)
        
        return min(10.0, structure_score)
    
    def _score_energy(self, transcript: str) -> float:
        """Score energy based on text analysis"""
        energy_score = 5.0  # Base score
        
        # Exclamations increase energy
        energy_score += min(2.0, transcript.count('!') * 0.5)
        
        # Action words increase energy
        action_words = ['run', 'jump', 'move', 'create', 'build', 'develop', 'grow', 'expand']
        action_count = sum(1 for word in transcript.lower().split() if word in action_words)
        energy_score += min(2.0, action_count * 0.3)
        
        # Capitalization indicates energy
        caps_count = sum(1 for char in transcript if char.isupper())
        energy_score += min(1.0, caps_count * 0.01)
        
        return min(10.0, energy_score)
    
    def _score_professionalism(self, transcript: str) -> float:
        """Score professionalism based on text analysis"""
        professionalism_score = 7.0  # Base score
        
        # Swear words decrease professionalism
        swear_words = ['damn', 'hell', 'crap', 'shit', 'fuck', 'ass']
        swear_count = sum(1 for word in transcript.lower().split() if word in swear_words)
        professionalism_score -= min(3.0, swear_count * 0.5)
        
        # Formal language increases professionalism
        formal_words = ['therefore', 'consequently', 'furthermore', 'moreover', 'additionally']
        formal_count = sum(1 for word in transcript.lower().split() if word in formal_words)
        professionalism_score += min(2.0, formal_count * 0.3)
        
        return max(1.0, min(10.0, professionalism_score))
    
    def _generate_local_feedback(self, transcript: str, metrics: ContentMetrics, 
                                scores: FeedbackScore, analysis_depth: str) -> Dict:
        """Generate feedback based on local analysis"""
        feedback = {
            "summary": self._generate_summary(metrics, scores),
            "strengths": self._identify_strengths(scores),
            "areas_for_improvement": self._identify_improvements(scores),
            "specific_suggestions": self._generate_suggestions(transcript, scores),
            "next_steps": self._suggest_next_steps(scores)
        }
        
        if analysis_depth in ["comprehensive", "expert"]:
            feedback["detailed_analysis"] = self._detailed_analysis(transcript, metrics, scores)
        
        return feedback
    
    def _generate_summary(self, metrics: ContentMetrics, scores: FeedbackScore) -> str:
        """Generate summary feedback"""
        overall = scores.overall_score
        
        if overall >= 8.0:
            return f"Excellent podcast content! Your {metrics.word_count} words demonstrate strong engagement and clarity."
        elif overall >= 6.0:
            return f"Good podcast content with room for improvement. Your {metrics.word_count} words show potential."
        else:
            return f"Your content has potential but needs work. Focus on the areas below to improve your {metrics.word_count} words."
    
    def _identify_strengths(self, scores: FeedbackScore) -> List[str]:
        """Identify content strengths"""
        strengths = []
        
        if scores.clarity >= 7.0:
            strengths.append("Clear communication and easy to follow")
        if scores.engagement >= 7.0:
            strengths.append("Engaging content that holds attention")
        if scores.structure >= 7.0:
            strengths.append("Well-structured and organized")
        if scores.energy >= 7.0:
            strengths.append("Energetic and dynamic delivery")
        if scores.professionalism >= 7.0:
            strengths.append("Professional and polished presentation")
        
        if not strengths:
            strengths.append("Content shows potential for improvement")
        
        return strengths
    
    def _identify_improvements(self, scores: FeedbackScore) -> List[str]:
        """Identify areas for improvement"""
        improvements = []
        
        if scores.clarity < 6.0:
            improvements.append("Improve clarity and readability")
        if scores.engagement < 6.0:
            improvements.append("Increase audience engagement")
        if scores.structure < 6.0:
            improvements.append("Better organize your content structure")
        if scores.energy < 6.0:
            improvements.append("Add more energy and enthusiasm")
        if scores.professionalism < 6.0:
            improvements.append("Enhance professional presentation")
        
        return improvements
    
    def _generate_suggestions(self, transcript: str, scores: FeedbackScore) -> List[str]:
        """Generate specific improvement suggestions"""
        suggestions = []
        
        if scores.clarity < 7.0:
            suggestions.append("Break long sentences into shorter, clearer ones")
            suggestions.append("Use more punctuation to improve readability")
        
        if scores.engagement < 7.0:
            suggestions.append("Ask more questions to involve your audience")
            suggestions.append("Use personal language (I, you, we) to connect")
        
        if scores.structure < 7.0:
            suggestions.append("Organize content into clear sections")
            suggestions.append("Use transition words to connect ideas")
        
        if scores.energy < 7.0:
            suggestions.append("Vary your tone and pace")
            suggestions.append("Use more dynamic language and examples")
        
        if scores.professionalism < 7.0:
            suggestions.append("Avoid informal language in professional contexts")
            suggestions.append("Use more formal transition words")
        
        return suggestions[:5]  # Limit to top 5
    
    def _suggest_next_steps(self, scores: FeedbackScore) -> List[str]:
        """Suggest next steps for improvement"""
        next_steps = []
        
        if scores.overall_score < 6.0:
            next_steps.append("Review and revise your content")
            next_steps.append("Practice reading your script aloud")
            next_steps.append("Get feedback from others")
        elif scores.overall_score < 8.0:
            next_steps.append("Focus on your weakest areas")
            next_steps.append("Record and review your delivery")
            next_steps.append("Study successful podcasters")
        else:
            next_steps.append("Maintain your high standards")
            next_steps.append("Experiment with new techniques")
            next_steps.append("Help others improve their content")
        
        return next_steps
    
    def _detailed_analysis(self, transcript: str, metrics: ContentMetrics, 
                          scores: FeedbackScore) -> Dict:
        """Generate detailed analysis for comprehensive/expert levels"""
        return {
            "word_analysis": {
                "total_words": metrics.word_count,
                "unique_words": metrics.unique_words,
                "vocabulary_diversity": round(metrics.unique_words / metrics.word_count, 3)
            },
            "timing_analysis": {
                "estimated_reading_time": f"{metrics.reading_time_minutes} minutes",
                "speaking_pace": f"{metrics.speaking_pace_wpm} words per minute",
                "content_density": "Medium" if 0.3 <= metrics.unique_words / metrics.word_count <= 0.7 else "High/Low"
            },
            "content_quality": {
                "topic_coherence": f"{metrics.topic_coherence_score * 100:.1f}%",
                "engagement_indicators": metrics.engagement_indicators,
                "overall_rating": "Excellent" if scores.overall_score >= 8.0 else "Good" if scores.overall_score >= 6.0 else "Needs Improvement"
            }
        }
    
    def _get_fallback_feedback(self, reason: str) -> Dict:
        """Provide fallback feedback when analysis fails"""
        return {
            "success": False,
            "error": reason,
            "feedback": {
                "summary": "Unable to analyze content at this time",
                "strengths": ["Content was provided for analysis"],
                "areas_for_improvement": ["Analysis service unavailable"],
                "specific_suggestions": ["Try again later or check your input"],
                "next_steps": ["Verify your transcript and retry"]
            },
            "analysis_type": "fallback"
        }
    
    def get_comparative_analysis(self, transcripts: List[str]) -> Dict:
        """Compare multiple transcripts"""
        if len(transcripts) < 2:
            return {"error": "Need at least 2 transcripts for comparison"}
        
        analyses = []
        for transcript in transcripts:
            analysis = self.analyze(transcript, analysis_depth="standard")
            analyses.append(analysis)
        
        # Simple comparison
        scores = [a.get("scores", {}).get("overall_score", 0) for a in analyses if a.get("success")]
        
        if not scores:
            return {"error": "No successful analyses to compare"}
        
        return {
            "success": True,
            "comparison": {
                "total_transcripts": len(transcripts),
                "average_score": round(sum(scores) / len(scores), 2),
                "best_score": max(scores),
                "worst_score": min(scores),
                "improvement_trend": "Improving" if len(scores) > 1 and scores[-1] > scores[0] else "Stable"
            },
            "individual_analyses": analyses
        }
    
    def clear_cache(self):
        """Clear the analysis cache"""
        self.analysis_cache.clear()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "cache_size": len(self.analysis_cache),
            "cache_ttl": self.cache_ttl,
            "cache_hits": 0,  # Simplified - no hit tracking in barebones version
            "cache_misses": 0
        }
