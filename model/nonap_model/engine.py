"""NoNap Detection Engine selector and orchestrator.

Selects between:
- 'baseline': MediaPipe Face Mesh EAR/MAR + temporal smoothing
- 'hybrid': YOLOv8 ROI localizer + ViT classifier + temporal smoothing
Based on DETECTOR_BACKEND env var and checkpoint availability.
"""

import os
import time
from typing import Dict, Optional
import numpy as np

from nonap_model.preprocess import preprocess_frame
from nonap_model.landmarks_baseline import LandmarksBaseline
from nonap_model.temporal import TemporalManager
from nonap_model.localizer import FaceROILocalizer
from nonap_model.vit_classifier import ViTClassifier


class DetectionEngine:
    """Orchestrates face detection, landmark extraction, and temporal drowsiness evaluation."""

    def __init__(self, backend_override: Optional[str] = None) -> None:
        # Determine backend from environment or override
        env_backend = (
            backend_override
            or os.environ.get("DETECTOR_BACKEND", "auto")
        ).lower()

        # Check for hybrid weights
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
        self.temporal_mgr = TemporalManager()

    def predict(
        self, frame_bgr: np.ndarray, driver_id: Optional[str] = None
    ) -> Dict[str, any]:
        """Process a single BGR frame and return complete drowsiness metrics.

        Args:
            frame_bgr: Input BGR image frame (numpy array).
            driver_id: Optional UUID string identifying the driver for temporal tracking.

        Returns:
            Dictionary matching the strict NoNap schema:
            {
                "status": "alert|drowsy|yawning|no_face",
                "confidence": float,
                "is_alert": bool,
                "metrics": {
                    "ear": float,
                    "mar": float,
                    "perclos": float,
                    "eyes_closed_s": float,
                    "yawns_5min": int,
                    "backend": "hybrid|baseline",
                    "latency_ms": float,
                    "night_mode": bool,
                    "severity": "low|medium|high|critical"
                }
            }
        """
        start_t = time.perf_counter()

        if frame_bgr is None or frame_bgr.size == 0:
            return {
                "status": "no_face",
                "confidence": 1.0,
                "is_alert": False,
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
        enhanced_frame, is_night_mode, _ = preprocess_frame(frame_bgr)

        # Step 2: Extract landmarks via MediaPipe FaceMesh
        lm_result = self.baseline.extract_landmarks(enhanced_frame)

        tracker = self.temporal_mgr.get_tracker(driver_id)
        now = time.time()

        if lm_result is None:
            # No face detected in this frame
            temporal_state = tracker.update(
                has_face=False, ear=0.0, mar=0.0, timestamp=now
            )
            latency_ms = (time.perf_counter() - start_t) * 1000.0

            return {
                "status": temporal_state["status"],
                "confidence": temporal_state["confidence"],
                "is_alert": temporal_state["is_alert"],
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

        ear = lm_result["ear"]
        mar = lm_result["mar"]
        face_bbox = lm_result["face_bbox"]

        # Step 3: Evaluate temporal state
        temporal_state = tracker.update(
            has_face=True, ear=ear, mar=mar, timestamp=now
        )

        status = temporal_state["status"]
        confidence = temporal_state["confidence"]
        severity = temporal_state["severity"]
        is_alert = temporal_state["is_alert"]

        # If running hybrid and ViT model is loaded, cross-verify with ViT
        if self.backend == "hybrid" and self.vit.is_loaded:
            rois = self.localizer.localize_rois(enhanced_frame, fallback_bbox=face_bbox)
            if rois and rois["eye_crop"].size > 0:
                vit_res = self.vit.classify_crop(rois["eye_crop"])
                if vit_res:
                    vit_status = vit_res["status"]
                    vit_conf = vit_res["confidence"]
                    # If ViT agrees on drowsy or yawning with high confidence, reinforce
                    if vit_status == status:
                        confidence = max(confidence, vit_conf)

        latency_ms = (time.perf_counter() - start_t) * 1000.0

        return {
            "status": status,
            "confidence": round(float(confidence), 2),
            "is_alert": is_alert,
            "face_bbox": face_bbox,
            "metrics": {
                "ear": round(float(ear), 3),
                "mar": round(float(mar), 3),
                "perclos": temporal_state["perclos"],
                "eyes_closed_s": temporal_state["eyes_closed_s"],
                "yawns_5min": temporal_state["yawns_5min"],
                "backend": self.backend,
                "latency_ms": round(latency_ms, 2),
                "night_mode": is_night_mode,
                "severity": severity,
            },
        }

    def close(self) -> None:
        """Release underlying vision resources."""
        self.baseline.close()


# Global engine singleton
_engine_instance: Optional[DetectionEngine] = None


def get_engine() -> DetectionEngine:
    """Return the global DetectionEngine singleton."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = DetectionEngine()
    return _engine_instance


def predict(
    frame_bgr: np.ndarray, driver_id: Optional[str] = None
) -> Dict[str, any]:
    """Top-level convenience prediction function."""
    return get_engine().predict(frame_bgr, driver_id=driver_id)
