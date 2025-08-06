# backend/error_tracker.py
import json
import os
import threading
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ErrorSeverity(Enum):
    """Error severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better organization"""

    AUDIO = "audio"
    TRANSCRIPTION = "transcription"
    AI_API = "ai_api"
    NETWORK = "network"
    CONFIGURATION = "configuration"
    UI = "ui"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass
class ErrorEvent:
    """Data class for error events"""

    timestamp: datetime
    error_type: str
    message: str
    severity: ErrorSeverity
    category: ErrorCategory
    component: str
    stack_trace: Optional[str] = None
    context: Optional[Dict] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    resolution_notes: Optional[str] = None


class ErrorTracker:
    """
    Lightweight error tracking system for SoapBoxx backend
    """

    def __init__(self, max_errors: int = 1000):
        self.max_errors = max_errors
        self.errors: List[ErrorEvent] = []
        self.error_counts: Dict[str, int] = {}
        self.severity_counts: Dict[ErrorSeverity, int] = {
            severity: 0 for severity in ErrorSeverity
        }
        self.category_counts: Dict[ErrorCategory, int] = {
            category: 0 for category in ErrorCategory
        }
        self.component_counts: Dict[str, int] = {}

        # Thread safety
        self._lock = threading.Lock()

        # Simple initialization without file I/O
        print("ErrorTracker initialized (lightweight mode)")

    def track_error(
        self,
        error_type: str,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        component: str = "unknown",
        exception: Optional[Exception] = None,
        context: Optional[Dict] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> ErrorEvent:
        """Track a new error"""
        try:
            # Create error event
            error = ErrorEvent(
                timestamp=datetime.now(),
                error_type=error_type,
                message=message,
                severity=severity,
                category=category,
                component=component,
                stack_trace=traceback.format_exc() if exception else None,
                context=context,
                user_id=user_id,
                session_id=session_id,
            )

            # Add to errors list
            with self._lock:
                self.errors.append(error)
                self._update_counts(error)

                # Limit errors to max_errors
                if len(self.errors) > self.max_errors:
                    self.errors = self.errors[-self.max_errors :]

            return error
        except Exception as e:
            # Fallback: just print the error
            print(f"ErrorTracker failed to track error: {e}")
            return None

    def get_errors(
        self,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None,
        component: Optional[str] = None,
        resolved: Optional[bool] = None,
        hours: Optional[int] = None,
    ) -> List[ErrorEvent]:
        """Get filtered errors"""
        try:
            with self._lock:
                filtered_errors = self.errors.copy()

            # Apply filters
            if severity:
                filtered_errors = [e for e in filtered_errors if e.severity == severity]

            if category:
                filtered_errors = [e for e in filtered_errors if e.category == category]

            if component:
                filtered_errors = [
                    e for e in filtered_errors if e.component == component
                ]

            if resolved is not None:
                filtered_errors = [e for e in filtered_errors if e.resolved == resolved]

            if hours:
                cutoff_time = datetime.now() - timedelta(hours=hours)
                filtered_errors = [
                    e for e in filtered_errors if e.timestamp >= cutoff_time
                ]

            return filtered_errors
        except Exception as e:
            print(f"ErrorTracker failed to get errors: {e}")
            return []

    def get_error_summary(self) -> Dict:
        """Get error summary statistics"""
        try:
            with self._lock:
                total_errors = len(self.errors)
                unresolved_errors = len([e for e in self.errors if not e.resolved])

                # Get recent errors (last 24 hours)
                cutoff_time = datetime.now() - timedelta(hours=24)
                recent_errors = len(
                    [e for e in self.errors if e.timestamp >= cutoff_time]
                )

                # Get severity breakdown
                severity_breakdown = {
                    severity.value: count
                    for severity, count in self.severity_counts.items()
                }

                # Get category breakdown
                category_breakdown = {
                    category.value: count
                    for category, count in self.category_counts.items()
                }

                # Get component breakdown
                component_breakdown = self.component_counts.copy()

            return {
                "total_errors": total_errors,
                "unresolved_errors": unresolved_errors,
                "recent_errors_24h": recent_errors,
                "severity_breakdown": severity_breakdown,
                "category_breakdown": category_breakdown,
                "component_breakdown": component_breakdown,
                "last_updated": datetime.now().isoformat(),
            }
        except Exception as e:
            print(f"ErrorTracker failed to get summary: {e}")
            return {
                "total_errors": 0,
                "unresolved_errors": 0,
                "recent_errors_24h": 0,
                "severity_breakdown": {},
                "category_breakdown": {},
                "component_breakdown": {},
                "last_updated": datetime.now().isoformat(),
            }

    def get_health_score(self) -> float:
        """Calculate system health score (0-100)"""
        try:
            summary = self.get_error_summary()

            # Start with perfect score
            score = 100.0

            # Penalize based on error counts and severity
            critical_penalty = summary["severity_breakdown"].get("critical", 0) * 20
            high_penalty = summary["severity_breakdown"].get("high", 0) * 10
            medium_penalty = summary["severity_breakdown"].get("medium", 0) * 5
            low_penalty = summary["severity_breakdown"].get("low", 0) * 1

            # Apply penalties
            score -= critical_penalty + high_penalty + medium_penalty + low_penalty

            # Ensure score is between 0 and 100
            return max(0.0, min(100.0, score))
        except Exception as e:
            print(f"ErrorTracker failed to get health score: {e}")
            return 100.0

    def _update_counts(self, error: ErrorEvent):
        """Update error counts"""
        try:
            # Update error type count
            self.error_counts[error.error_type] = (
                self.error_counts.get(error.error_type, 0) + 1
            )

            # Update severity count
            self.severity_counts[error.severity] += 1

            # Update category count
            self.category_counts[error.category] += 1

            # Update component count
            self.component_counts[error.component] = (
                self.component_counts.get(error.component, 0) + 1
            )
        except Exception as e:
            print(f"ErrorTracker failed to update counts: {e}")


# Global error tracker instance (lazy-loaded)
_error_tracker_instance = None


def get_error_tracker():
    """Get the global error tracker instance (lazy-loaded)"""
    global _error_tracker_instance
    if _error_tracker_instance is None:
        _error_tracker_instance = ErrorTracker()
    return _error_tracker_instance


# Convenience functions for easy error tracking
def track_error(error_type: str, message: str, **kwargs):
    """Convenience function to track an error"""
    try:
        return get_error_tracker().track_error(error_type, message, **kwargs)
    except Exception as e:
        print(f"Failed to track error: {e}")
        return None


def track_api_error(message: str, **kwargs):
    """Track API-related errors"""
    try:
        return get_error_tracker().track_error(
            error_type="APIError",
            message=message,
            category=ErrorCategory.AI_API,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )
    except Exception as e:
        print(f"Failed to track API error: {e}")
        return None


def track_audio_error(message: str, **kwargs):
    """Track audio-related errors"""
    try:
        return get_error_tracker().track_error(
            error_type="AudioError",
            message=message,
            category=ErrorCategory.AUDIO,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )
    except Exception as e:
        print(f"Failed to track audio error: {e}")
        return None


def track_transcription_error(message: str, **kwargs):
    """Track transcription-related errors"""
    try:
        return get_error_tracker().track_error(
            error_type="TranscriptionError",
            message=message,
            category=ErrorCategory.TRANSCRIPTION,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )
    except Exception as e:
        print(f"Failed to track transcription error: {e}")
        return None


def track_config_error(message: str, **kwargs):
    """Track configuration-related errors"""
    try:
        return get_error_tracker().track_error(
            error_type="ConfigurationError",
            message=message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )
    except Exception as e:
        print(f"Failed to track config error: {e}")
        return None


# Backward compatibility
error_tracker = get_error_tracker()
