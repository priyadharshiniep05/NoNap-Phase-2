"""Unit tests for the top-level DetectionEngine and predict() function."""

import numpy as np
from nonap_model.engine import DetectionEngine, predict


def test_predict_schema_synthetic_frame():
    """Verify predict returns exact required schema on synthetic frame."""
    frame = np.full((320, 240, 3), 100, dtype=np.uint8)
    res = predict(frame, driver_id="test_driver_1")

    assert "status" in res
    assert res["status"] in ("alert", "drowsy", "yawning", "no_face")
    assert "confidence" in res
    assert isinstance(res["confidence"], float)
    assert "is_alert" in res
    assert isinstance(res["is_alert"], bool)

    metrics = res["metrics"]
    for key in ("ear", "mar", "perclos", "eyes_closed_s", "yawns_5min", "backend", "latency_ms", "night_mode", "severity"):
        assert key in metrics

    assert metrics["backend"] in ("baseline", "hybrid")
    assert metrics["latency_ms"] >= 0.0


def test_engine_empty_frame():
    """Verify engine handles empty or None frames without crashing."""
    engine = DetectionEngine()
    res = engine.predict(None)

    assert res["status"] == "no_face"
    assert res["metrics"]["latency_ms"] == 0.0
