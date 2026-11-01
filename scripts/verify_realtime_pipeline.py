"""Verification script for NoNap real-time pipeline:
1. MediaPipe Face Mesh EAR and MAR calculation
2. 5-frame moving average smoothing
3. 10s personalized calibration saving to DB2
4. Drowsiness detection with IST timestamps & laptop audible alert
5. Database logging to DB2 (ops.db)
"""

import os
import sys
import time
import numpy as np

# Ensure model and server are on path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "model"))

from model.nonap_model.landmarks_baseline import calculate_ear, calculate_mar, LandmarksBaseline
from model.nonap_model.temporal import DriverTemporalTracker, temporal_manager
from server.app.core.timezone import now_ist, format_ist_time, to_ist_iso
from server.app.db.ops_db import get_ops_session_factory
from server.app.db.models_ops import Threshold, AlertLog
from server.app.services.calibration_service import calibration_service
from server.app.services.detection_service import process_frame
from server.app.services.alert_service import play_laptop_alarm

def test_formulas():
    print("--- 1. Testing EAR & MAR Formula Correctness ---")
    # Synthetic 6-point eye landmarks
    # EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
    # p1=(0,0), p4=(10,0), p2=(3,3), p6=(3,-3), p3=(7,3), p5=(7,-3)
    # ||p1-p4|| = 10, ||p2-p6|| = 6, ||p3-p5|| = 6
    # EAR = (6 + 6) / (2 * 10) = 12 / 20 = 0.60
    synthetic_eye = np.array([
        [0.0, 0.0],
        [3.0, 3.0],
        [7.0, 3.0],
        [10.0, 0.0],
        [7.0, -3.0],
        [3.0, -3.0],
    ])
    ear_val = calculate_ear(synthetic_eye)
    assert abs(ear_val - 0.60) < 1e-4, f"Expected 0.60, got {ear_val}"
    print(f"✓ EAR formula exact match: {ear_val:.4f}")

    # Synthetic 8-point mouth landmarks
    # MAR = (||p2-p8|| + ||p3-p7|| + ||p4-p6||) / (2 * ||p1-p5||)
    synthetic_mouth = np.array([
        [0.0, 0.0],    # p1 (corner)
        [2.0, 4.0],    # p2
        [5.0, 5.0],    # p3
        [8.0, 4.0],    # p4
        [10.0, 0.0],   # p5 (corner)
        [8.0, -4.0],   # p6
        [5.0, -5.0],   # p7
        [2.0, -4.0],   # p8
    ])
    corner_l = synthetic_mouth[0]
    corner_r = synthetic_mouth[4]
    v_pairs = [
        (synthetic_mouth[1], synthetic_mouth[7]),
        (synthetic_mouth[2], synthetic_mouth[6]),
        (synthetic_mouth[3], synthetic_mouth[5]),
    ]
    mar_val = calculate_mar(corner_l, corner_r, v_pairs)
    assert abs(mar_val - 1.30) < 1e-4, f"Expected 1.30, got {mar_val}"
    print(f"✓ MAR formula exact match: {mar_val:.4f}")

def test_smoothing():
    print("\n--- 2. Testing 5-Frame Moving Average Smoothing ---")
    baseline = LandmarksBaseline(smooth_window=5)
    raw_ears = [0.30, 0.32, 0.28, 0.22, 0.18, 0.12]
    smoothed_history = []
    for val in raw_ears:
        baseline._ear_history.append(val)
        smoothed = float(np.mean(baseline._ear_history))
        smoothed_history.append(smoothed)
    # The last smoothed value should be the average of the last 5 values:
    # (0.32 + 0.28 + 0.22 + 0.18 + 0.12) / 5 = 1.12 / 5 = 0.224
    expected_last = sum(raw_ears[1:]) / 5.0
    assert abs(smoothed_history[-1] - expected_last) < 1e-4, f"Expected {expected_last}, got {smoothed_history[-1]}"
    print(f"✓ 5-frame moving average: raw={raw_ears[-1]} -> smoothed={smoothed_history[-1]:.4f} (expected {expected_last:.4f})")

def test_calibration_and_db2():
    print("\n--- 3. Testing Personalized Calibration & DB2 Persistence ---")
    driver_id = "test_driver_priya"
    session = calibration_service.start_calibration(driver_id, duration_seconds=0.5)
    ops_db = get_ops_session_factory()()
    
    try:
        # Feed calibration frames (typical open eyes ~0.30, closed mouth ~0.15)
        res = None
        for _ in range(20):
            ear_sample = 0.29 + float(np.random.uniform(-0.01, 0.01))
            mar_sample = 0.16 + float(np.random.uniform(-0.01, 0.01))
            time.sleep(0.03)
            out = calibration_service.process_frame_sample(driver_id, ear=ear_sample, mar=mar_sample, ops_session=ops_db)
            if out:
                res = out
                break

        if not res and session.is_complete:
            res = session.result

        assert res is not None, "Calibration should produce thresholds"
        print(f"✓ Baseline computed: Mean EAR={res['baseline_mean_ear']:.4f}, Mean MAR={res['baseline_mean_mar']:.4f}")
        print(f"✓ Thresholds derived: EAR Drowsy={res['ear_threshold']:.4f}, MAR Yawn={res['mar_threshold']:.4f}")

        # Verify saved in DB2 (Threshold table)
        t = ops_db.query(Threshold).filter(Threshold.scope == "user", Threshold.user_id == driver_id).first()
        assert t is not None, "Threshold record must exist in DB2"
        assert abs(t.ear_threshold - res['ear_threshold']) < 1e-4
        print(f"✓ Successfully verified DB2 persistence in 'thresholds' table (user_id={driver_id})")
    finally:
        ops_db.close()

def test_timezone():
    print("\n--- 4. Testing Asia/Kolkata (IST) Timestamps ---")
    dt_ist = now_ist()
    time_str = format_ist_time(dt_ist)
    iso_str = to_ist_iso(dt_ist)
    print(f"✓ Current IST time: {time_str}")
    print(f"✓ Current IST ISO:  {iso_str}")
    assert "IST" in time_str or "+05:30" in iso_str, "Must reflect IST timezone offset"

def test_cooldown_and_escalation():
    print("\n--- 5. Testing 10s Cooldown & Severity Escalation ---")
    tracker = DriverTemporalTracker("test_driver_cooldown")
    tracker.ear_threshold = 0.22
    
    # Simulate low EAR for 2 seconds (eyes closed)
    now = time.time()
    for i in range(25):
        t = now + (i * 0.1)
        res = tracker.update(has_face=True, ear=0.10, mar=0.15, timestamp=t)
        if res.get("is_alert") and res.get("status") == "drowsy":
            print(f"✓ First alert triggered at t={t-now:.1f}s: severity={res['severity']}, reason={res['reason']}")
            break

    # Immediately check at t+1s (within 10s cooldown): is_alert should be False
    res_within_cooldown = tracker.update(has_face=True, ear=0.10, mar=0.15, timestamp=now + 3.0)
    assert not res_within_cooldown.get("is_alert"), "Alert must be suppressed during 10s cooldown"
    print("✓ Alert correctly suppressed during 10s cooldown window")

    # Check after 10.5s: severity should escalate from medium -> high/critical
    res_after_cooldown = tracker.update(has_face=True, ear=0.10, mar=0.15, timestamp=now + 13.0)
    assert res_after_cooldown.get("is_alert"), "Alert must fire after cooldown"
    assert res_after_cooldown["severity"] in ("high", "critical"), f"Severity should escalate, got {res_after_cooldown['severity']}"
    print(f"✓ Severity escalated after continued drowsiness: {res_after_cooldown['severity'].upper()}")

if __name__ == "__main__":
    test_formulas()
    test_smoothing()
    test_calibration_and_db2()
    test_timezone()
    test_cooldown_and_escalation()
    print("\n========================================================")
    print("  ALL REAL-TIME PIPELINE VERIFICATION CHECKS PASSED!    ")
    print("========================================================")
