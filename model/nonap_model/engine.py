"""NoNap Detection Engine selector and orchestrator.

Selects between:
- 'baseline': MediaPipe Face Mesh EAR/MAR + temporal smoothing
- 'hybrid': YOLOv8 ROI localizer + ViT classifier + temporal smoothing
Based on DETECTOR_BACKEND env var and checkpoint availability.
"""

import os
import time
from typing import Dict, Optional, Any
import numpy as np

from nonap_model.preprocess import preprocess_frame
from nonap_model.landmarks_baseline import LandmarksBaseline
from nonap_model.temporal import TemporalManager, temporal_manager
from nonap_model.localizer import FaceROILocalizer
from nonap_model.vit_classifier import ViTClassifier


class DetectionEngine:
    """Orchestrates face detection, landmark extraction, and temporal drowsiness evaluation."""

    def __init__(self, backend_override: Optional[str] = None) -> None:
        env_backend = (
            backend_override
            or os.environ.get("DETECTOR_BACKEND", "auto")
        ).lower()

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        vit_checkpoint = os.path.join(base_dir, "checkpoints", "vit_drowsy.pt")
        has_vit = os.path.exists(vit_checkpoint)

        self.localizer = FaceROILocalizer()
        has_localizer = self.localizer.model is not None

        if env_backend == "hybrid" or (env_backend == "auto" and has_vit and has_localizer):
            self.backend = "hybrid"
            self.vit = ViTClassifier(checkpoint_path=vit_checkpoint)
        else:
            self.backend = "baseline"
            self.vit = ViTClassifier()

        self.baseline = LandmarksBaseline()
        self.temporal_mgr = temporal_manager

    def predict(
        self,
        frame_bgr: Optional[np.ndarray] = None,
        driver_id: Optional[str] = None,
        frame: Optional[np.ndarray] = None,
        custom_thresholds: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process a single BGR frame and return complete drowsiness metrics."""
        img = frame if frame is not None else frame_bgr
        start_t = time.perf_counter()

        # Update custom thresholds on the driver's tracker if provided
        tracker = self.temporal_mgr.get_tracker(
            driver_id,
            ear_threshold=custom_thresholds.get("ear") if custom_thresholds else None,
            mar_threshold=custom_thresholds.get("mar") if custom_thresholds else None,
        )

        if img is None or img.size == 0:
            return {
                "driver_id": driver_id or "",
                "status": "no_face",
                "face_detected": False,
                "raw_ear": 0.0,
                "raw_mar": 0.0,
                "severity": "low",
                "confidence": 1.0,
                "is_alert": False,
                "alert_triggered": False,
                "alert_type": None,
                "reason": None,
                "ear": 0.0,
                "mar": 0.0,
                "perclos": 0.0,
                "eyes_closed_seconds": 0.0,
                "backend": self.backend,
                "latency_ms": 0.0,
                "timestamp": time.time(),
                "metrics": {
                    "ear": 0.0,
                    "mar": 0.0,
                    "perclos": 0.0,
                    "eyes_closed_s": 0.0,
                    "yawns_5min": 0,
                    "backend": self.backend,
                    "latency_ms": 0.0,
                    "night_mode": False,
                    "severity": "low",
                },
            }

        # Step 1: Preprocess with CLAHE and night mode detection
        enhanced_frame, is_night_mode, _ = preprocess_frame(img)

        # Step 2: Extract real-time landmarks via MediaPipe FaceMesh
        lm_result = self.baseline.extract_landmarks(enhanced_frame)
        now = time.time()

        if lm_result is None:
            temporal_state = tracker.update(
                has_face=False, ear=0.0, mar=0.0, timestamp=now
            )
            latency_ms = (time.perf_counter() - start_t) * 1000.0

            return {
                "driver_id": driver_id or "",
                "status": temporal_state["status"],
                "face_detected": False,
                "raw_ear": 0.0,
                "raw_mar": 0.0,
                "severity": temporal_state["severity"],
                "confidence": temporal_state["confidence"],
                "is_alert": temporal_state["is_alert"],
                "alert_triggered": temporal_state["is_alert"],
                "alert_type": temporal_state.get("alert_type"),
                "reason": temporal_state.get("reason"),
                "ear": 0.0,
                "mar": 0.0,
                "perclos": temporal_state["perclos"],
                "eyes_closed_seconds": temporal_state["eyes_closed_s"],
                "backend": self.backend,
                "latency_ms": round(latency_ms, 2),
                "timestamp": now,
                "face_bbox": None,
                "metrics": {
                    "ear": 0.0,
                    "mar": 0.0,
                    "perclos": temporal_state["perclos"],
                    "eyes_closed_s": temporal_state["eyes_closed_s"],
                    "yawns_5min": temporal_state["yawns_5min"],
                    "backend": self.backend,
                    "latency_ms": round(latency_ms, 2),
                    "night_mode": is_night_mode,
                    "severity": temporal_state["severity"],
                },
            }

        ear = float(lm_result["ear"])
        mar = float(lm_result["mar"])
        face_bbox = lm_result["face_bbox"]

        # Step 3: Evaluate temporal state
        temporal_state = tracker.update(
            has_face=True, ear=ear, mar=mar, timestamp=now
        )

        status = temporal_state["status"]
        confidence = temporal_state["confidence"]
        severity = temporal_state["severity"]
        is_alert = temporal_state["is_alert"]
        alert_type = temporal_state.get("alert_type")
        reason = temporal_state.get("reason")

        # Step 4: Hybrid ViT reinforcement if weights available
        if self.backend == "hybrid" and self.vit.is_loaded:
            rois = self.localizer.localize_rois(enhanced_frame, fallback_bbox=face_bbox)
            if rois and rois["eye_crop"].size > 0:
                vit_res = self.vit.classify_crop(rois["eye_crop"])
                if vit_res:
                    if vit_res["status"] == status:
                        confidence = max(confidence, vit_res["confidence"])

        latency_ms = (time.perf_counter() - start_t) * 1000.0

        return {
            "driver_id": driver_id or "",
            "status": status,
            "face_detected": True,
            # Unsmoothed per-frame values: the 5-frame moving average lags ~1.7 s
            # at the Pi's 3 fps, so time-window alert levels use these.
            "raw_ear": float(lm_result.get("raw_ear", ear)),
            "raw_mar": float(lm_result.get("raw_mar", mar)),
            "severity": severity,
            "confidence": round(float(confidence), 2),
            "is_alert": is_alert,
            "alert_triggered": is_alert,
            "alert_type": alert_type,
            "reason": reason,
            "ear": round(ear, 3),
            "mar": round(mar, 3),
            "perclos": temporal_state["perclos"],
            "eyes_closed_seconds": temporal_state["eyes_closed_s"],
            "backend": self.backend,
            "latency_ms": round(latency_ms, 2),
            "timestamp": now,
            "face_bbox": face_bbox,
            "metrics": {
                "ear": round(ear, 3),
                "mar": round(mar, 3),
                "perclos": temporal_state["perclos"],
                "eyes_closed_s": temporal_state["eyes_closed_s"],
                "yawns_5min": temporal_state["yawns_5min"],
                "backend": self.backend,
                "latency_ms": round(latency_ms, 2),
                "night_mode": is_night_mode,
                "severity": severity,
            },
            # Allow .to_dict() duck typing
            "to_dict": lambda: None,
        }

    def close(self) -> None:
        """Release underlying vision resources."""
        self.baseline.close()


_engine_instance: Optional[DetectionEngine] = None


def get_engine() -> DetectionEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = DetectionEngine()
    return _engine_instance


def predict(
    frame: Optional[np.ndarray] = None,
    frame_bgr: Optional[np.ndarray] = None,
    driver_id: Optional[str] = None,
    custom_thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Top-level convenience prediction function."""
    return get_engine().predict(
        frame_bgr=frame_bgr,
        frame=frame,
        driver_id=driver_id,
        custom_thresholds=custom_thresholds,
    )
