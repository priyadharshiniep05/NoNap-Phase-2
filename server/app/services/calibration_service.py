"""Per-person facial baseline calibration service for NoNap.

Calibrates open-eye EAR and closed-mouth MAR over a 10-second period:
- EAR drowsy threshold = min(0.75 * mean_ear, mean_ear - 2 * std_ear)
- MAR yawn threshold = max(0.55, mean_mar + 3 * std_mar)
- Automatically persists to DB2 (Threshold table with scope='user')
- Updates active temporal tracker in memory
"""

import logging
import time
from typing import Dict, List, Optional, Any
import numpy as np
from sqlalchemy.orm import Session

from server.app.db.models_ops import Threshold
from model.nonap_model.temporal import temporal_manager

logger = logging.getLogger("nonap.calibration")


class DriverCalibrationSession:
    """Tracks calibration data for a single driver."""

    def __init__(self, driver_id: str, duration_seconds: float = 10.0):
        self.driver_id = driver_id
        self.duration_seconds = duration_seconds
        self.start_time = time.time()
        self.ear_samples: List[float] = []
        self.mar_samples: List[float] = []
        self.is_active = True
        self.is_complete = False
        self.result: Optional[Dict[str, Any]] = None

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.duration_seconds - self.elapsed_seconds)

    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed_seconds / self.duration_seconds)

    def add_sample(self, ear: float, mar: float) -> bool:
        """Add sample during calibration. Returns True if calibration just finished."""
        if not self.is_active:
            return False

        if ear > 0.05 and mar > 0.02:  # valid face metrics
            self.ear_samples.append(ear)
            self.mar_samples.append(mar)

        if self.elapsed_seconds >= self.duration_seconds and len(self.ear_samples) >= 15:
            self.is_active = False
            self.is_complete = True
            return True

        return False

    def compute_thresholds(self) -> Dict[str, Any]:
        """Compute baseline metrics and derived thresholds from calibration samples."""
        if not self.ear_samples or not self.mar_samples:
            # Fallback to standard safe defaults if insufficient samples
            return {
                "ear_threshold": 0.21,
                "mar_threshold": 0.60,
                "baseline_mean_ear": 0.28,
                "baseline_std_ear": 0.03,
                "baseline_mean_mar": 0.15,
                "baseline_std_mar": 0.05,
                "samples_count": 0,
            }

        mean_ear = float(np.mean(self.ear_samples))
        std_ear = float(np.std(self.ear_samples))
        mean_mar = float(np.mean(self.mar_samples))
        std_mar = float(np.std(self.mar_samples))

        # EAR Drowsy Threshold: 0.75 * mean_ear or mean - 2*std, clamped safely
        calc_ear = min(0.75 * mean_ear, mean_ear - 2.0 * std_ear)
        ear_threshold = round(float(np.clip(calc_ear, 0.16, 0.26)), 3)

        # MAR Yawn Threshold: mean_mar + 3*std with safe floor of 0.55
        calc_mar = max(0.55, mean_mar + 3.0 * std_mar)
        mar_threshold = round(float(np.clip(calc_mar, 0.55, 0.75)), 3)

        self.result = {
            "ear_threshold": ear_threshold,
            "mar_threshold": mar_threshold,
            "baseline_mean_ear": round(mean_ear, 3),
            "baseline_std_ear": round(std_ear, 3),
            "baseline_mean_mar": round(mean_mar, 3),
            "baseline_std_mar": round(std_mar, 3),
            "samples_count": len(self.ear_samples),
        }
        return self.result


class CalibrationService:
    """Coordinates driver calibration sessions and updates DB2 thresholds."""

    def __init__(self):
        self._sessions: Dict[str, DriverCalibrationSession] = {}

    def start_calibration(self, driver_id: str, duration_seconds: float = 10.0) -> DriverCalibrationSession:
        """Start a new 10-second calibration session for the driver."""
        session = DriverCalibrationSession(driver_id, duration_seconds)
        self._sessions[driver_id] = session
        logger.info(f"Started baseline calibration for driver {driver_id} ({duration_seconds}s)")
        return session

    def is_calibrating(self, driver_id: str) -> bool:
        session = self._sessions.get(driver_id)
        return session is not None and session.is_active

    def get_session(self, driver_id: str) -> Optional[DriverCalibrationSession]:
        return self._sessions.get(driver_id)

    def process_frame_sample(
        self,
        driver_id: str,
        ear: float,
        mar: float,
        ops_session: Session,
    ) -> Optional[Dict[str, Any]]:
        """Feed a live frame sample into the calibration session.

        If calibration finishes, saves thresholds to DB2 and updates tracker.
        """
        session = self._sessions.get(driver_id)
        if not session or not session.is_active:
            return None

        finished = session.add_sample(ear, mar)
        if finished:
            thresholds = session.compute_thresholds()
            self._save_thresholds_to_db(driver_id, thresholds, ops_session)
            # Update temporal tracker in memory
            tracker = temporal_manager.get_tracker(driver_id)
            tracker.update_thresholds(
                ear_threshold=thresholds["ear_threshold"],
                mar_threshold=thresholds["mar_threshold"],
            )
            logger.info(
                f"Calibration complete for driver {driver_id}: "
                f"EAR threshold={thresholds['ear_threshold']}, MAR threshold={thresholds['mar_threshold']}"
            )
            return thresholds

        return None

    def _save_thresholds_to_db(self, driver_id: str, data: Dict[str, Any], ops_session: Session) -> None:
        """Persist calibrated thresholds to ops_db."""
        try:
            thresh = (
                ops_session.query(Threshold)
                .filter(Threshold.scope == "user", Threshold.user_id == driver_id)
                .first()
            )
            if not thresh:
                thresh = Threshold(
                    scope="user",
                    user_id=driver_id,
                    ear_threshold=data["ear_threshold"],
                    mar_threshold=data["mar_threshold"],
                    perclos_threshold=0.40,
                    eyes_closed_seconds=1.5,
                    alert_cooldown_seconds=10.0,
                )
                ops_session.add(thresh)
            else:
                thresh.ear_threshold = data["ear_threshold"]
                thresh.mar_threshold = data["mar_threshold"]
                thresh.alert_cooldown_seconds = 10.0

            ops_session.commit()
            logger.info(f"Persisted personalized thresholds for driver {driver_id} to ops_db.")
        except Exception as e:
            ops_session.rollback()
            logger.error(f"Failed to persist thresholds to ops_db: {e}")


# Global calibration service singleton
calibration_service = CalibrationService()
