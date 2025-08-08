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
        **kwargs: Any,
    ) -> ErrorEvent:
        """Track a new error with enhanced parameter validation"""
        try:
            # Validate required parameters
            if not error_type or not isinstance(error_type, str):
                error_type = "UnknownError"
            if not message or not isinstance(message, str):
                message = "No error message provided"
            
            # Merge any extra metadata into context for storage
            if kwargs:
                context = {**(context or {}), **kwargs}

            # Get stack trace if exception provided
            stack_trace = None
            if exception:
                stack_trace = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))

            # Create error event
            error = ErrorEvent(
                timestamp=datetime.now(),
                error_type=error_type,
                message=message,
                severity=severity,
                category=category,
                component=component,
                stack_trace=stack_trace,
                context=context,
                user_id=user_id,
                session_id=session_id,
            )

            # Thread-safe addition
            with self._lock:
                self.errors.append(error)
                self._update_counts(error)

                # Maintain max errors limit
                if len(self.errors) > self.max_errors:
                    self.errors.pop(0)

            return error

        except Exception as e:
            print(f"ErrorTracker failed to track error: {e}")
            # Return a minimal error event as fallback
            return ErrorEvent(
                timestamp=datetime.now(),
                error_type="ErrorTrackerFailure",
                message=f"Failed to track error: {str(e)}",
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.SYSTEM,
                component="error_tracker"
            )

    def get_errors(
        self,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None,
        component: Optional[str] = None,
        resolved: Optional[bool] = None,
        hours: Optional[int] = None,
    ) -> List[ErrorEvent]:
        """Get filtered errors with enhanced error handling"""
        try:
            with self._lock:
                filtered_errors = self.errors.copy()

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
        """Get error summary statistics with enhanced error handling"""
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
        """Calculate system health score (0-100) with enhanced error handling"""
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
            print(f"ErrorTracker failed to calculate health score: {e}")
            return 0.0

    def _update_counts(self, error: ErrorEvent):
        """Update error counts with enhanced error handling"""
        try:
            # Update error type counts
            self.error_counts[error.error_type] = self.error_counts.get(error.error_type, 0) + 1

            # Update severity counts
            self.severity_counts[error.severity] = self.severity_counts.get(error.severity, 0) + 1

            # Update category counts
            self.category_counts[error.category] = self.category_counts.get(error.category, 0) + 1

            # Update component counts
            self.component_counts[error.component] = self.component_counts.get(error.component, 0) + 1
        except Exception as e:
            print(f"ErrorTracker failed to update counts: {e}")


# Global error tracker instance
_error_tracker: Optional[ErrorTracker] = None


def get_error_tracker() -> ErrorTracker:
    """Get or create global error tracker instance"""
    global _error_tracker
    if _error_tracker is None:
        _error_tracker = ErrorTracker()
    return _error_tracker


# Convenience functions with enhanced error handling and consistent signatures
def track_error(error_type: str, message: str, **kwargs) -> Optional[ErrorEvent]:
    """Convenience function to track an error with enhanced validation"""
    try:
        return get_error_tracker().track_error(error_type, message, **kwargs)
    except Exception as e:
        print(f"Failed to track error: {e}")
        return None


def track_api_error(message: str, severity: ErrorSeverity = ErrorSeverity.HIGH, **kwargs) -> Optional[ErrorEvent]:
    """Track API-related errors with enhanced validation"""
    try:
        return get_error_tracker().track_error(
            error_type="APIError",
            message=message,
            category=ErrorCategory.AI_API,
            severity=severity,
            **kwargs,
        )
    except Exception as e:
        print(f"Failed to track API error: {e}")
        return None


def track_audio_error(message: str, **kwargs) -> Optional[ErrorEvent]:
    """Track audio-related errors with enhanced validation"""
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


def track_transcription_error(message: str, **kwargs) -> Optional[ErrorEvent]:
    """Track transcription-related errors with enhanced validation"""
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


def track_config_error(message: str, **kwargs) -> Optional[ErrorEvent]:
    """Track configuration-related errors with enhanced validation"""
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


def track_ui_error(message: str, **kwargs) -> Optional[ErrorEvent]:
    """Track UI-related errors with enhanced validation"""
    try:
        return get_error_tracker().track_error(
            error_type="UIError",
            message=message,
            category=ErrorCategory.UI,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )
    except Exception as e:
        print(f"Failed to track UI error: {e}")
        return None


def track_user_action(action: str, duration: float = None, success: bool = True, **kwargs) -> Optional[ErrorEvent]:
    """Track user actions for UX analytics with enhanced validation"""
    try:
        # Convert user action to error tracking format for monitoring
        severity = ErrorSeverity.LOW if success else ErrorSeverity.MEDIUM
        message = f"User action: {action} {'succeeded' if success else 'failed'}"
        if duration:
            message += f" (duration: {duration:.2f}s)"
        
        return get_error_tracker().track_error(
            error_type="UserAction",
            message=message,
            category=ErrorCategory.UI,  # User actions are UI-related
            severity=severity,
            context={"action": action, "duration": duration, "success": success, **kwargs}
        )
    except Exception as e:
        print(f"Failed to track user action: {e}")
        return None


def get_ui_performance_metrics() -> Dict:
    """Get UI performance metrics with enhanced error handling"""
    try:
        tracker = get_error_tracker()
        
        ui_errors = [e for e in tracker.errors if e.error_type in ["UIError"]]
        user_actions = [e for e in tracker.errors if e.error_type == "UserAction"]
        
        successful_actions = [a for a in user_actions if a.context and a.context.get("success", True)]
        failed_actions = [a for a in user_actions if a.context and not a.context.get("success", True)]
        
        success_rate = len(successful_actions) / len(user_actions) if user_actions else 1.0
        
        # Calculate average duration for successful actions
        durations = [a.context.get("duration", 0) for a in successful_actions if a.context and a.context.get("duration")]
        average_duration = sum(durations) / len(durations) if durations else 0.0
        
        return {
            "total_ui_errors": len(ui_errors),
            "total_user_actions": len(user_actions),
            "successful_actions": len(successful_actions),
            "failed_actions": len(failed_actions),
            "success_rate": success_rate,
            "average_action_duration": average_duration,
            "recent_errors": [e.message for e in ui_errors[-5:]]  # Last 5 errors
        }
        
    except Exception as e:
        print(f"Failed to get UI performance metrics: {e}")
        return {}


# Backward compatibility
error_tracker = get_error_tracker()
