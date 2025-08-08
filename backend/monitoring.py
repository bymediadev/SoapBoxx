#!/usr/bin/env python3
"""
Monitoring and Telemetry System for SoapBoxx
Comprehensive performance monitoring, error tracking, and user analytics
"""

import json
import os
import sys
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import traceback

# Try to import psutil for system monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available. Install with: pip install psutil")

# Try to import error tracker
try:
    from .error_tracker import ErrorTracker, ErrorEvent, ErrorSeverity, ErrorCategory, get_error_tracker
except ImportError:
    try:
        from error_tracker import ErrorTracker, ErrorEvent, ErrorSeverity, ErrorCategory, get_error_tracker
    except ImportError:
        print("Warning: error_tracker not available")
        # Create placeholder classes
        class ErrorTracker:
            def __init__(self): pass
            def get_errors(self, hours=None): return []
            def get_error_summary(self): return {}
        class ErrorEvent: pass
        class ErrorSeverity:
            LOW = "low"
            MEDIUM = "medium"
            HIGH = "high"
            CRITICAL = "critical"
        class ErrorCategory:
            AUDIO = "audio"
            TRANSCRIPTION = "transcription"
            AI_API = "ai_api"
            NETWORK = "network"
            CONFIGURATION = "configuration"
            UI = "ui"
            SYSTEM = "system"
            UNKNOWN = "unknown"
        
        # Define get_error_tracker function
        def get_error_tracker():
            return ErrorTracker()


@dataclass
class PerformanceMetric:
    """Data class for performance metrics"""
    timestamp: datetime
    operation: str
    duration: float
    success: bool
    error_message: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class UserAction:
    """Data class for user actions"""
    timestamp: datetime
    action: str
    component: str
    duration: float
    success: bool
    error_message: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class SystemHealth:
    """Data class for system health metrics"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_threads: int
    error_count: int
    performance_score: float


class PerformanceMonitor:
    """Comprehensive performance monitoring system"""
    
    def __init__(self, max_metrics: int = 1000):
        self.max_metrics = max_metrics
        self.metrics: List[PerformanceMetric] = []
        self.operation_stats: Dict[str, Dict] = defaultdict(lambda: {
            'count': 0,
            'total_duration': 0.0,
            'success_count': 0,
            'error_count': 0,
            'min_duration': float('inf'),
            'max_duration': 0.0
        })
        self._lock = threading.Lock()
        
    def track_operation(self, operation: str, duration: float, success: bool = True, 
                       error_message: Optional[str] = None, metadata: Optional[Dict] = None):
        """Track a performance metric"""
        try:
            metric = PerformanceMetric(
                timestamp=datetime.now(),
                operation=operation,
                duration=duration,
                success=success,
                error_message=error_message,
                metadata=metadata or {}
            )
            
            with self._lock:
                self.metrics.append(metric)
                
                # Update operation statistics
                stats = self.operation_stats[operation]
                stats['count'] += 1
                stats['total_duration'] += duration
                stats['min_duration'] = min(stats['min_duration'], duration)
                stats['max_duration'] = max(stats['max_duration'], duration)
                
                if success:
                    stats['success_count'] += 1
                else:
                    stats['error_count'] += 1
                
                # Maintain max metrics limit
                if len(self.metrics) > self.max_metrics:
                    self.metrics.pop(0)
                    
        except Exception as e:
            print(f"Failed to track performance metric: {e}")
    
    def get_operation_stats(self, operation: Optional[str] = None) -> Dict:
        """Get performance statistics for operations"""
        try:
            with self._lock:
                if operation:
                    if operation in self.operation_stats:
                        stats = self.operation_stats[operation].copy()
                        if stats['count'] > 0:
                            stats['avg_duration'] = stats['total_duration'] / stats['count']
                            stats['success_rate'] = stats['success_count'] / stats['count']
                        else:
                            stats['avg_duration'] = 0.0
                            stats['success_rate'] = 0.0
                        return stats
                    else:
                        return {}
                else:
                    # Return all operation stats
                    all_stats = {}
                    for op, stats in self.operation_stats.items():
                        all_stats[op] = stats.copy()
                        if stats['count'] > 0:
                            all_stats[op]['avg_duration'] = stats['total_duration'] / stats['count']
                            all_stats[op]['success_rate'] = stats['success_count'] / stats['count']
                        else:
                            all_stats[op]['avg_duration'] = 0.0
                            all_stats[op]['success_rate'] = 0.0
                    return all_stats
                    
        except Exception as e:
            print(f"Failed to get operation stats: {e}")
            return {}
    
    def get_recent_metrics(self, hours: int = 24) -> List[PerformanceMetric]:
        """Get recent performance metrics"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            with self._lock:
                return [m for m in self.metrics if m.timestamp >= cutoff_time]
        except Exception as e:
            print(f"Failed to get recent metrics: {e}")
            return []


class UserAnalytics:
    """User analytics and behavior tracking"""
    
    def __init__(self, max_actions: int = 1000):
        self.max_actions = max_actions
        self.actions: List[UserAction] = []
        self.user_sessions: Dict[str, Dict] = defaultdict(lambda: {
            'start_time': None,
            'end_time': None,
            'action_count': 0,
            'error_count': 0,
            'total_duration': 0.0
        })
        self._lock = threading.Lock()
        
    def track_action(self, action: str, component: str, duration: float = 0.0,
                    success: bool = True, error_message: Optional[str] = None,
                    metadata: Optional[Dict] = None, session_id: Optional[str] = None):
        """Track a user action"""
        try:
            user_action = UserAction(
                timestamp=datetime.now(),
                action=action,
                component=component,
                duration=duration,
                success=success,
                error_message=error_message,
                metadata=metadata or {}
            )
            
            with self._lock:
                self.actions.append(user_action)
                
                # Update session statistics
                if session_id:
                    session = self.user_sessions[session_id]
                    if session['start_time'] is None:
                        session['start_time'] = user_action.timestamp
                    session['action_count'] += 1
                    session['total_duration'] += duration
                    if not success:
                        session['error_count'] += 1
                
                # Maintain max actions limit
                if len(self.actions) > self.max_actions:
                    self.actions.pop(0)
                    
        except Exception as e:
            print(f"Failed to track user action: {e}")
    
    def get_user_analytics(self, hours: int = 24) -> Dict:
        """Get user analytics summary"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            with self._lock:
                recent_actions = [a for a in self.actions if a.timestamp >= cutoff_time]
                
                if not recent_actions:
                    return {
                        'total_actions': 0,
                        'success_rate': 0.0,
                        'avg_duration': 0.0,
                        'top_actions': [],
                        'top_components': [],
                        'error_rate': 0.0
                    }
                
                # Calculate statistics
                total_actions = len(recent_actions)
                successful_actions = [a for a in recent_actions if a.success]
                success_rate = len(successful_actions) / total_actions if total_actions > 0 else 0.0
                
                durations = [a.duration for a in recent_actions if a.duration > 0]
                avg_duration = sum(durations) / len(durations) if durations else 0.0
                
                # Top actions
                action_counts = defaultdict(int)
                for action in recent_actions:
                    action_counts[action.action] += 1
                top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                
                # Top components
                component_counts = defaultdict(int)
                for action in recent_actions:
                    component_counts[action.component] += 1
                top_components = sorted(component_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                
                # Error rate
                error_count = len([a for a in recent_actions if not a.success])
                error_rate = error_count / total_actions if total_actions > 0 else 0.0
                
                return {
                    'total_actions': total_actions,
                    'success_rate': success_rate,
                    'avg_duration': avg_duration,
                    'top_actions': top_actions,
                    'top_components': top_components,
                    'error_rate': error_rate
                }
                
        except Exception as e:
            print(f"Failed to get user analytics: {e}")
            return {}


class SystemMonitor:
    """System resource monitoring"""
    
    def __init__(self):
        self.health_history: deque = deque(maxlen=100)
        self._lock = threading.Lock()
        
    def get_system_health(self) -> SystemHealth:
        """Get current system health metrics"""
        try:
            # CPU usage
            if PSUTIL_AVAILABLE:
                cpu_usage = psutil.cpu_percent(interval=1)
            else:
                cpu_usage = 0.0
            
            # Memory usage
            if PSUTIL_AVAILABLE:
                memory = psutil.virtual_memory()
                memory_usage = memory.percent
            else:
                memory_usage = 0.0
            
            # Disk usage
            if PSUTIL_AVAILABLE:
                try:
                    disk = psutil.disk_usage('/')
                    disk_usage = disk.percent
                except:
                    disk_usage = 0.0
            else:
                disk_usage = 0.0
            
            # Active threads
            active_threads = threading.active_count()
            
            # Error count (from error tracker)
            try:
                error_tracker = get_error_tracker()
                error_count = len(error_tracker.get_errors(hours=1))
            except:
                error_count = 0
            
            # Calculate performance score (0-100)
            performance_score = 100.0
            performance_score -= cpu_usage * 0.5  # CPU penalty
            performance_score -= memory_usage * 0.3  # Memory penalty
            performance_score -= disk_usage * 0.2  # Disk penalty
            performance_score -= error_count * 5  # Error penalty
            performance_score = max(0.0, min(100.0, performance_score))
            
            health = SystemHealth(
                timestamp=datetime.now(),
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                disk_usage=disk_usage,
                active_threads=active_threads,
                error_count=error_count,
                performance_score=performance_score
            )
            
            with self._lock:
                self.health_history.append(health)
            
            return health
            
        except Exception as e:
            print(f"Failed to get system health: {e}")
            return SystemHealth(
                timestamp=datetime.now(),
                cpu_usage=0.0,
                memory_usage=0.0,
                disk_usage=0.0,
                active_threads=0,
                error_count=0,
                performance_score=0.0
            )
    
    def get_health_history(self, hours: int = 24) -> List[SystemHealth]:
        """Get system health history"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            with self._lock:
                return [h for h in self.health_history if h.timestamp >= cutoff_time]
        except Exception as e:
            print(f"Failed to get health history: {e}")
            return []


class TelemetryManager:
    """Main telemetry manager that coordinates all monitoring systems"""
    
    def __init__(self):
        self.performance_monitor = PerformanceMonitor()
        self.user_analytics = UserAnalytics()
        self.system_monitor = SystemMonitor()
        self.error_tracker = get_error_tracker()
        
        # Start monitoring thread
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        
    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self._monitoring_active:
            try:
                # Collect system health
                health = self.system_monitor.get_system_health()
                
                # Log if performance is poor
                if health.performance_score < 50:
                    print(f"⚠️ System performance degraded: {health.performance_score:.1f}/100")
                
                # Sleep for monitoring interval
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                print(f"Monitoring loop error: {e}")
                time.sleep(60)  # Wait longer on error
    
    def track_operation(self, operation: str, duration: float, success: bool = True,
                       error_message: Optional[str] = None, metadata: Optional[Dict] = None):
        """Track an operation with telemetry"""
        self.performance_monitor.track_operation(operation, duration, success, error_message, metadata)
    
    def track_user_action(self, action: str, component: str, duration: float = 0.0,
                         success: bool = True, error_message: Optional[str] = None,
                         metadata: Optional[Dict] = None, session_id: Optional[str] = None):
        """Track a user action with telemetry"""
        self.user_analytics.track_action(action, component, duration, success, error_message, metadata, session_id)
    
    def get_telemetry_summary(self) -> Dict:
        """Get comprehensive telemetry summary"""
        try:
            # Get performance metrics
            performance_stats = self.performance_monitor.get_operation_stats()
            
            # Get user analytics
            user_analytics = self.user_analytics.get_user_analytics()
            
            # Get system health
            system_health = self.system_monitor.get_system_health()
            
            # Get error summary
            try:
                error_summary = self.error_tracker.get_error_summary()
            except:
                error_summary = {}
            
            return {
                'timestamp': datetime.now().isoformat(),
                'performance': performance_stats,
                'user_analytics': user_analytics,
                'system_health': asdict(system_health),
                'error_summary': error_summary,
                'overall_health_score': system_health.performance_score
            }
            
        except Exception as e:
            print(f"Failed to get telemetry summary: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': f"Failed to get telemetry summary: {str(e)}"
            }
    
    def export_telemetry_data(self, filepath: str) -> bool:
        """Export telemetry data to JSON file"""
        try:
            telemetry_data = {
                'export_timestamp': datetime.now().isoformat(),
                'performance_metrics': [asdict(m) for m in self.performance_monitor.metrics],
                'user_actions': [asdict(a) for a in self.user_analytics.actions],
                'system_health_history': [asdict(h) for h in self.system_monitor.health_history],
                'error_summary': self.error_tracker.get_error_summary() if hasattr(self.error_tracker, 'get_error_summary') else {}
            }
            
            with open(filepath, 'w') as f:
                json.dump(telemetry_data, f, indent=2, default=str)
            
            return True
            
        except Exception as e:
            print(f"Failed to export telemetry data: {e}")
            return False
    
    def cleanup(self):
        """Cleanup telemetry manager"""
        self._monitoring_active = False
        if self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=5)


# Global telemetry manager instance
_telemetry_manager: Optional[TelemetryManager] = None


def get_telemetry_manager() -> TelemetryManager:
    """Get or create global telemetry manager"""
    global _telemetry_manager
    if _telemetry_manager is None:
        _telemetry_manager = TelemetryManager()
    return _telemetry_manager


def track_operation(operation: str, duration: float, success: bool = True,
                   error_message: Optional[str] = None, metadata: Optional[Dict] = None):
    """Track an operation with telemetry"""
    try:
        manager = get_telemetry_manager()
        manager.track_operation(operation, duration, success, error_message, metadata)
    except Exception as e:
        print(f"Failed to track operation: {e}")


def track_user_action(action: str, component: str, duration: float = 0.0,
                     success: bool = True, error_message: Optional[str] = None,
                     metadata: Optional[Dict] = None, session_id: Optional[str] = None):
    """Track a user action with telemetry"""
    try:
        manager = get_telemetry_manager()
        manager.track_user_action(action, component, duration, success, error_message, metadata, session_id)
    except Exception as e:
        print(f"Failed to track user action: {e}")


def get_telemetry_summary() -> Dict:
    """Get telemetry summary"""
    try:
        manager = get_telemetry_manager()
        return manager.get_telemetry_summary()
    except Exception as e:
        print(f"Failed to get telemetry summary: {e}")
        return {'error': str(e)}


def export_telemetry_data(filepath: str) -> bool:
    """Export telemetry data"""
    try:
        manager = get_telemetry_manager()
        return manager.export_telemetry_data(filepath)
    except Exception as e:
        print(f"Failed to export telemetry data: {e}")
        return False
