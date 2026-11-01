"""Unit tests for driver temporal state and drowsiness tracking logic."""

from nonap_model.temporal import DriverTemporalTracker


def test_normal_alert_state():
    """Verify normal EAR and MAR values result in alert status."""
    tracker = DriverTemporalTracker()
    now = 1000.0

    # Normal open eyes (EAR 0.32) and closed mouth (MAR 0.20)
    res = tracker.update(has_face=True, ear=0.32, mar=0.20, timestamp=now)
    assert res["status"] == "alert"
    assert not res["is_alert"]
    assert res["eyes_closed_s"] == 0.0


def test_micro_blink_filtering():
    """Verify micro-blinks under 0.4s are not counted towards drowsiness."""
    tracker = DriverTemporalTracker()
    start_t = 1000.0

    # 1. Open eyes
    tracker.update(has_face=True, ear=0.30, mar=0.20, timestamp=start_t)

    # 2. Quick blink for 0.25s (closed)
    res = tracker.update(has_face=True, ear=0.15, mar=0.20, timestamp=start_t + 0.25)
    # Filtered out because duration < 0.4s
    assert res["status"] == "alert"
    assert res["eyes_closed_s"] == 0.0

    # 3. Eyes reopened
    res = tracker.update(has_face=True, ear=0.30, mar=0.20, timestamp=start_t + 0.35)
    assert res["status"] == "alert"
    assert res["eyes_closed_s"] == 0.0


def test_drowsiness_prolonged_closure():
    """Verify eye closure for >= 1.5s triggers drowsy status."""
    tracker = DriverTemporalTracker(eyes_closed_seconds=1.5)
    start_t = 1000.0

    # Eyes close at start_t
    tracker.update(has_face=True, ear=0.15, mar=0.20, timestamp=start_t)
    # Eyes closed for 1.0s (not yet threshold)
    res = tracker.update(has_face=True, ear=0.15, mar=0.20, timestamp=start_t + 1.0)
    assert res["status"] == "alert"

    # Eyes closed for 1.6s -> triggers drowsy (medium severity)
    res = tracker.update(has_face=True, ear=0.15, mar=0.20, timestamp=start_t + 1.6)
    assert res["status"] == "drowsy"
    assert res["severity"] == "medium"
    assert res["is_alert"] is True
    assert res["eyes_closed_s"] >= 1.5


def test_high_severity_drowsiness():
    """Verify continuous eye closure >= 3.0s triggers high severity."""
    tracker = DriverTemporalTracker()
    start_t = 1000.0

    # Eyes closed for 3.2s
    tracker.update(has_face=True, ear=0.12, mar=0.20, timestamp=start_t)
    res = tracker.update(has_face=True, ear=0.12, mar=0.20, timestamp=start_t + 3.2)
    assert res["status"] == "drowsy"
    assert res["severity"] == "high"


def test_yawning_detection():
    """Verify mouth opening >= 1.0s triggers yawning status."""
    tracker = DriverTemporalTracker(mar_threshold=0.60)
    start_t = 1000.0

    # Normal
    tracker.update(has_face=True, ear=0.30, mar=0.20, timestamp=start_t)
    # Mouth open for 0.5s (not yet yawn)
    res = tracker.update(has_face=True, ear=0.30, mar=0.75, timestamp=start_t + 0.5)
    assert res["status"] == "alert"

    # Mouth open for 1.2s (starts at 1000.5 -> reaches 1001.7 = 1.2s duration)
    res = tracker.update(has_face=True, ear=0.30, mar=0.75, timestamp=start_t + 1.7)
    assert res["status"] == "yawning"
    assert res["severity"] == "low"
    assert res["is_alert"] is True


def test_alert_cooldown():
    """Verify subsequent alerts are throttled within the 30s cooldown."""
    tracker = DriverTemporalTracker(alert_cooldown_seconds=30.0)
    start_t = 1000.0

    # First alert at 1.6s
    tracker.update(has_face=True, ear=0.12, mar=0.20, timestamp=start_t)
    res1 = tracker.update(has_face=True, ear=0.12, mar=0.20, timestamp=start_t + 1.6)
    assert res1["is_alert"] is True

    # Same drowsy condition at 5.0s -> status still drowsy, but is_alert is False due to cooldown
    res2 = tracker.update(has_face=True, ear=0.12, mar=0.20, timestamp=start_t + 5.0)
    assert res2["status"] == "drowsy"
    assert res2["is_alert"] is False

    # After cooldown (31s later)
    res3 = tracker.update(has_face=True, ear=0.12, mar=0.20, timestamp=start_t + 33.0)
    assert res3["status"] == "drowsy"
    assert res3["is_alert"] is True


def test_no_face_timeout():
    """Verify absence of face for > 5s yields no_face status."""
    tracker = DriverTemporalTracker()
    start_t = 1000.0

    # Face seen at start_t
    tracker.update(has_face=True, ear=0.30, mar=0.20, timestamp=start_t)

    # Face missing for 2s
    res1 = tracker.update(has_face=False, ear=0.0, mar=0.0, timestamp=start_t + 2.0)
    assert res1["status"] != "no_face"

    # Face missing for 6s
    res2 = tracker.update(has_face=False, ear=0.0, mar=0.0, timestamp=start_t + 6.0)
    assert res2["status"] == "no_face"
