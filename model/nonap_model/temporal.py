"""Temporal logic and state tracking for driver drowsiness detection.

Maintains per-driver rolling windows (30s) to calculate:
- PERCLOS (Percentage of Eye Closure)
- Continuous eye closure duration (with micro-blink filtering)
- Continuous yawn duration
- Yawn frequency over 5 minutes
- 10-second alert cooldown and escalation tracking
- Reason for drowsiness alert: 'eyes_closed', 'yawn', 'perclos'
"""

from collections import deque
import time
from typing import Deque, Dict, Optional, Tuple


class DriverTemporalTracker:
    """Tracks temporal metrics and computes drowsiness status for a single driver."""

    def __init__(
        self,
        ear_threshold: float = 0.21,
        mar_threshold: float = 0.60,
        perclos_threshold: float = 0.40,
        eyes_closed_seconds: float = 1.5,
        alert_cooldown_seconds: float = 10.0,
        window_seconds: float = 30.0,
    ) -> None:
        self.ear_threshold = ear_threshold
        self.mar_threshold = mar_threshold
        self.perclos_threshold = perclos_threshold
        self.eyes_closed_seconds = eyes_closed_seconds
        self.alert_cooldown_seconds = alert_cooldown_seconds
        self.window_seconds = window_seconds

        # Rolling observation frames within 30s window: (timestamp, is_eyes_closed, is_yawning)
        self.history: Deque[Tuple[float, bool, bool]] = deque()

        # Eye closure tracking
        self.eyes_closed_start_time: Optional[float] = None
        self.current_closed_duration: float = 0.0

        # Yawn tracking
        self.yawn_start_time: Optional[float] = None
        self.current_yawn_duration: float = 0.0
        self.yawn_events_5min: Deque[float] = deque()

        # Face presence tracking
        self.last_face_seen_time: float = time.time()

        # Alert cooldown & escalation tracking: alert_type -> last_alert_time
        self.last_alert_times: Dict[str, float] = {}
        self.continuous_drowsy_duration: float = 0.0

    def update_thresholds(
        self,
        ear_threshold: Optional[float] = None,
        mar_threshold: Optional[float] = None,
        perclos_threshold: Optional[float] = None,
        eyes_closed_seconds: Optional[float] = None,
    ) -> None:
        """Update driver's personalized thresholds."""
        if ear_threshold is not None:
            self.ear_threshold = ear_threshold
        if mar_threshold is not None:
            self.mar_threshold = mar_threshold
        if perclos_threshold is not None:
            self.perclos_threshold = perclos_threshold
        if eyes_closed_seconds is not None:
            self.eyes_closed_seconds = eyes_closed_seconds

    def update(
        self,
        has_face: bool,
        ear: float,
        mar: float,
        timestamp: Optional[float] = None,
    ) -> Dict[str, any]:
        """Update tracker with frame metrics and return evaluated temporal state.

        Args:
            has_face: True if face was detected in current frame.
            ear: Current Eye Aspect Ratio.
            mar: Current Mouth Aspect Ratio.
            timestamp: Frame capture timestamp in epoch seconds (defaults to now).

        Returns:
            Dictionary containing derived status, severity, confidence, reason, and metrics.
        """
        now = timestamp if timestamp is not None else time.time()

        # Handle face presence
        if has_face:
            self.last_face_seen_time = now
        time_since_face = now - self.last_face_seen_time

        if not has_face:
            # If no face for > 3 seconds, report no_face status
            if time_since_face > 3.0:
                self.continuous_drowsy_duration = 0.0
                return {
                    "status": "no_face",
                    "severity": "low",
                    "confidence": 0.95,
                    "is_alert": False,
                    "alert_type": None,
                    "reason": None,
                    "perclos": self._calculate_perclos(now),
                    "eyes_closed_s": 0.0,
                    "yawns_5min": self._count_yawns_5min(now),
                    "ear_threshold": self.ear_threshold,
                    "mar_threshold": self.mar_threshold,
                }

        # Determine instantaneous states based on personalized thresholds
        is_eyes_closed = has_face and (ear < self.ear_threshold)
        is_yawning = has_face and (mar > self.mar_threshold)

        # Update eye closure duration
        if is_eyes_closed:
            if self.eyes_closed_start_time is None:
                self.eyes_closed_start_time = now
            self.current_closed_duration = now - self.eyes_closed_start_time
        else:
            self.eyes_closed_start_time = None
            self.current_closed_duration = 0.0

        # Update yawn duration
        if is_yawning:
            if self.yawn_start_time is None:
                self.yawn_start_time = now
            self.current_yawn_duration = now - self.yawn_start_time
            # Sustained yawn >= 1.0s counted as a yawn event
            if self.current_yawn_duration >= 1.0:
                if not self.yawn_events_5min or (now - self.yawn_events_5min[-1] > 3.0):
                    self.yawn_events_5min.append(now)
        else:
            self.yawn_start_time = None
            self.current_yawn_duration = 0.0

        # Append to rolling 30s history
        self.history.append((now, is_eyes_closed, is_yawning))
        self._prune_history(now)

        perclos = self._calculate_perclos(now)
        yawns_5min = self._count_yawns_5min(now)

        # Filter micro-blinks: normal blinks under 0.4s are ignored
        effective_closed_s = (
            self.current_closed_duration
            if self.current_closed_duration >= 0.4
            else 0.0
        )

        status = "alert"
        severity = "low"
        is_alert = False
        alert_type = None
        reason = None
        confidence = 0.85

        # Check statistical validity of PERCLOS (requires >= 10s of history)
        window_duration = (self.history[-1][0] - self.history[0][0]) if len(self.history) >= 2 else 0.0
        perclos_active = (window_duration >= 10.0 and len(self.history) >= 20 and perclos >= self.perclos_threshold)

        # 1. Drowsiness condition: continuous closure >= eyes_closed_seconds OR PERCLOS >= threshold
        if effective_closed_s >= self.eyes_closed_seconds or perclos_active:
            status = "drowsy"
            alert_type = "drowsy"
            self.continuous_drowsy_duration += 0.1

            if effective_closed_s >= self.eyes_closed_seconds:
                reason = "eyes_closed"
            else:
                reason = "perclos"

            # Severity escalation:
            # - Critical: continuous eye closure >= 5.0s
            # - High: closure >= 3.0s OR yawns_5min >= 3 OR PERCLOS >= 0.60
            # - Medium: closure 1.5s - 3.0s
            if effective_closed_s >= 5.0:
                severity = "critical"
                confidence = 0.98
            elif effective_closed_s >= 3.0 or yawns_5min >= 3 or (window_duration >= 10.0 and perclos >= 0.60):
                severity = "high"
                confidence = 0.95
            else:
                severity = "medium"
                confidence = 0.90

            if self._can_trigger_alert("drowsy", now):
                is_alert = True
                self.last_alert_times["drowsy"] = now

        # 2. Yawning condition: sustained yawn >= 1.0s
        elif self.current_yawn_duration >= 1.0:
            status = "yawning"
            alert_type = "yawning"
            reason = "yawn"
            severity = "low" if yawns_5min < 3 else "medium"
            confidence = 0.88
            self.continuous_drowsy_duration = 0.0

            if self._can_trigger_alert("yawning", now):
                is_alert = True
                self.last_alert_times["yawning"] = now
        else:
            self.continuous_drowsy_duration = 0.0

        return {
            "status": status,
            "severity": severity,
            "confidence": float(confidence),
            "is_alert": is_alert,
            "alert_type": alert_type,
            "reason": reason,
            "perclos": round(float(perclos), 3),
            "eyes_closed_s": round(float(effective_closed_s), 2),
            "yawns_5min": int(yawns_5min),
            "ear_threshold": round(self.ear_threshold, 3),
            "mar_threshold": round(self.mar_threshold, 3),
        }

    def _can_trigger_alert(self, alert_type: str, now: float) -> bool:
        """Enforce alert cooldown period (10s) per alert type to prevent alert spam."""
        last_time = self.last_alert_times.get(alert_type, 0.0)
        return (now - last_time) >= self.alert_cooldown_seconds

    def _prune_history(self, now: float) -> None:
        """Remove observations older than window_seconds (30s)."""
        cutoff = now - self.window_seconds
        while self.history and self.history[0][0] < cutoff:
            self.history.popleft()

    def _calculate_perclos(self, now: float) -> float:
        """Calculate percentage of eye closure over the window."""
        if not self.history:
            return 0.0
        closed_count = sum(1 for _, closed, _ in self.history if closed)
        return closed_count / len(self.history)

    def _count_yawns_5min(self, now: float) -> int:
        """Return the number of distinct yawn events in the last 5 minutes."""
        cutoff = now - 300.0
        while self.yawn_events_5min and self.yawn_events_5min[0] < cutoff:
            self.yawn_events_5min.popleft()
        return len(self.yawn_events_5min)

    def reset(self) -> None:
        """Reset temporal state."""
        self.history.clear()
        self.eyes_closed_start_time = None
        self.current_closed_duration = 0.0
        self.yawn_start_time = None
        self.current_yawn_duration = 0.0
        self.yawn_events_5min.clear()
        self.last_alert_times.clear()
        self.continuous_drowsy_duration = 0.0


class TemporalManager:
    """Manages temporal state per driver ID."""

    def __init__(self) -> None:
        self.trackers: Dict[str, DriverTemporalTracker] = {}

    def get_tracker(
        self,
        driver_id: Optional[str] = None,
        ear_threshold: Optional[float] = None,
        mar_threshold: Optional[float] = None,
    ) -> DriverTemporalTracker:
        key = driver_id or "default_driver"
        if key not in self.trackers:
            tracker = DriverTemporalTracker()
            if ear_threshold is not None:
                tracker.ear_threshold = ear_threshold
            if mar_threshold is not None:
                tracker.mar_threshold = mar_threshold
            self.trackers[key] = tracker
        else:
            if ear_threshold is not None:
                self.trackers[key].ear_threshold = ear_threshold
            if mar_threshold is not None:
                self.trackers[key].mar_threshold = mar_threshold
        return self.trackers[key]


# Global temporal manager singleton
temporal_manager = TemporalManager()
