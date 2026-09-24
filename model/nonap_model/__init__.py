"""NoNap Real-Time Drowsiness Detection Model Package.

Exports top-level predict(frame, driver_id=None) function.
"""

from nonap_model.engine import predict, get_engine, DetectionEngine
from nonap_model.preprocess import preprocess_frame
from nonap_model.landmarks_baseline import calculate_ear, calculate_mar
from nonap_model.temporal import DriverTemporalTracker, TemporalManager

__all__ = [
    "predict",
    "get_engine",
    "DetectionEngine",
    "preprocess_frame",
    "calculate_ear",
    "calculate_mar",
    "DriverTemporalTracker",
    "TemporalManager",
]
