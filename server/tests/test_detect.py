"""Tests for detection ingest, simulation, and accident SOS."""

import base64
import numpy as np
import cv2


def test_detect_frame_endpoint(client, test_driver):
    # Encode dummy 64x64 test image
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)
    b64_str = base64.b64encode(buf.tobytes()).decode("utf-8")

    payload = {
        "driver_id": test_driver.id,
        "frame_b64": b64_str,
        "source": "pi",
    }
    res = client.post("/detect/frame", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["driver_id"] == test_driver.id
    assert "status" in data
    assert "confidence" in data
    assert "backend" in data


def test_dev_simulate_drowsy(client, test_driver):
    payload = {
        "driver_id": test_driver.id,
        "event": "drowsy",
        "severity": "high",
        "confidence": 0.95,
        "ear": 0.12,
        "mar": 0.20,
        "perclos": 0.55,
    }
    res = client.post("/dev/simulate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "alert_broadcasted"
    assert data["event"] == "drowsy"
    assert "alert_id" in data


def test_accident_sos_alert(client, driver_headers, test_driver):
    payload = {
        "driver_id": test_driver.id,
        "confidence": 1.0,
        "details": "Accident SOS test",
    }
    res = client.post("/alerts/accident", json=payload, headers=driver_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "accident"
    assert data["severity"] == "critical"
    assert data["driver_id"] == test_driver.id


def test_monitor_status(client):
    res = client.get("/monitor/status")
    assert res.status_code == 200
    data = res.json()
    assert "is_running" in data
    assert "fps" in data
