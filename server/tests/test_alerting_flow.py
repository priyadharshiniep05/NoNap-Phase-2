"""Integration tests: Pi frames endpoint, level escalation, acknowledgement, devices, WS scoping.

The detection model is replaced by a stub that returns a scripted EAR per frame,
and the alerting/device clocks are driven by the test, so timing is exact.
"""

import asyncio

import cv2
import numpy as np
import pytest

import server.app.services.detection_service as detection_service
from server.app.core.config import get_settings
from server.app.db.models_ops import AlertLog
from server.app.services.alerting_service import alerting_service
from server.app.services.device_service import device_service
from server.app.db.auth_db import get_auth_session_factory
from server.app.db.ops_db import get_ops_session_factory

KEY = {"X-Device-Key": get_settings().DEVICE_API_KEY}
JPEG = cv2.imencode(".jpg", np.zeros((240, 320, 3), dtype=np.uint8))[1].tobytes()


class FakeClock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def scripted(monkeypatch):
    """Stub model + controllable clock. Set scripted.ear before each frame."""

    class Script:
        ear = 0.30
        mar = 0.15
        face = True
        clock = FakeClock()

    def fake_predict(frame=None, driver_id=None, custom_thresholds=None, **_):
        return {
            "driver_id": driver_id, "status": "alert", "face_detected": Script.face,
            "ear": Script.ear, "mar": Script.mar, "raw_ear": Script.ear, "raw_mar": Script.mar,
            "perclos": 0.0, "confidence": 0.9, "backend": "stub", "latency_ms": 1.0,
        }

    monkeypatch.setattr(detection_service, "model_predict", fake_predict)
    monkeypatch.setattr(detection_service, "MODEL_AVAILABLE", True)
    monkeypatch.setattr(get_settings(), "VIDEO_SOURCE", "pi")
    monkeypatch.setattr(get_settings(), "TELEMETRY_HZ", 1000.0)
    alerting_service.reset()
    device_service.reset()
    alerting_service.clock = Script.clock
    device_service.clock = Script.clock
    yield Script
    alerting_service.reset()
    device_service.reset()
    import time
    alerting_service.clock = time.time
    device_service.clock = time.time


def post_frame(client, driver, script, ear, dt=1 / 3, device="pi-test-01"):
    script.ear = ear
    script.clock.t += dt
    res = client.post(
        "/api/v1/frames",
        files={"frame": ("f.jpg", JPEG, "image/jpeg")},
        data={"device_id": device, "driver_id": driver, "captured_at": str(int(script.clock.t * 1000))},
        headers=KEY,
    )
    assert res.status_code == 200, res.text
    return res.json()


def close_eyes(client, driver, script, seconds):
    out = None
    for _ in range(int(round(seconds * 3))):
        out = post_frame(client, driver, script, 0.10)
    return out


def test_frames_requires_device_key(client, test_driver):
    res = client.post(
        "/api/v1/frames",
        files={"frame": ("f.jpg", JPEG, "image/jpeg")},
        data={"device_id": "x", "driver_id": test_driver.id},
    )
    assert res.status_code == 401


def test_frames_rejected_in_webcam_mode(client, test_driver, scripted, monkeypatch):
    monkeypatch.setattr(get_settings(), "VIDEO_SOURCE", "webcam")
    res = client.post(
        "/api/v1/frames",
        files={"frame": ("f.jpg", JPEG, "image/jpeg")},
        data={"device_id": "x", "driver_id": test_driver.id},
        headers=KEY,
    )
    assert res.status_code == 409


def test_frames_awake_by_email(client, test_driver, scripted):
    body = post_frame(client, test_driver.email, scripted, 0.30)
    assert body["state"] == "awake" and body["severity"] == 0 and body["alert_id"] is None


def test_real_model_on_blank_frame_reports_no_face(client, test_driver, monkeypatch):
    """No stub: the real pipeline must report no_face, never invented metrics."""
    monkeypatch.setattr(get_settings(), "VIDEO_SOURCE", "pi")
    alerting_service.reset()
    res = client.post(
        "/api/v1/frames",
        files={"frame": ("f.jpg", JPEG, "image/jpeg")},
        data={"device_id": "pi-blank", "driver_id": test_driver.id},
        headers=KEY,
    )
    assert res.status_code == 200
    assert res.json()["state"] in ("no_face", "error")
    assert res.json()["severity"] == 0


def test_eyes_closed_2s_reaches_level2_and_one_alert_row(client, test_driver, scripted, ops_db):
    before = ops_db.query(AlertLog).filter(AlertLog.driver_id == test_driver.id).count()
    post_frame(client, test_driver.id, scripted, 0.30)
    body = close_eyes(client, test_driver.id, scripted, 1.4)
    assert body["severity"] == 1 and body["state"] == "drowsy"
    body = close_eyes(client, test_driver.id, scripted, 1.0)
    assert body["severity"] == 2
    ops_db.expire_all()
    rows = ops_db.query(AlertLog).filter(AlertLog.driver_id == test_driver.id).count()
    assert rows == before + 1  # one episode, one alert (upgraded in place)
    a = ops_db.query(AlertLog).filter(AlertLog.id == body["alert_id"]).first()
    assert a.level == 2 and a.status == "active" and a.source == "pi" and a.device_id == "pi-test-01"


def test_unacknowledged_level2_escalates_to_level3_after_10s(client, test_driver, scripted, ops_db):
    post_frame(client, test_driver.id, scripted, 0.30)
    body = close_eyes(client, test_driver.id, scripted, 2.4)
    assert body["severity"] == 2
    alert_id = body["alert_id"]

    scripted.clock.t += 9.0
    assert asyncio.run(alerting_service.check_escalations(get_ops_session_factory())) == 0
    scripted.clock.t += 1.5
    # The app's own watchdog shares this clock and may get there first; assert the outcome.
    asyncio.run(alerting_service.check_escalations(get_ops_session_factory()))

    ops_db.expire_all()
    a = ops_db.query(AlertLog).filter(AlertLog.id == alert_id).first()
    assert a.level == 3 and a.status == "unacknowledged" and a.escalated_at is not None
    assert post_frame(client, test_driver.id, scripted, 0.30)["severity"] == 3


def test_ack_stops_alert_and_records_response_time(client, test_driver, driver_headers, scripted, ops_db):
    post_frame(client, test_driver.id, scripted, 0.30)
    body = close_eyes(client, test_driver.id, scripted, 2.4)
    alert_id = body["alert_id"]
    level2_at = scripted.clock.t  # last frame pushed it to L2 at or before this time

    scripted.clock.t += 3.4
    res = client.post(f"/api/v1/alerts/{alert_id}/ack", headers=driver_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "acknowledged" and data["acknowledged"] is True
    assert data["acknowledged_at"].endswith("+05:30")
    assert 3400 <= data["response_time_ms"] <= 3400 + (level2_at - scripted.clock.t + 3.4) * 1000 + 700

    # The Pi's poll sees it acknowledged, and the next frame is quiet.
    polled = client.get(f"/api/v1/alerts/{alert_id}", headers=KEY).json()
    assert polled["status"] == "acknowledged"
    assert post_frame(client, test_driver.id, scripted, 0.30)["severity"] == 0

    # Acknowledged alerts never escalate.
    scripted.clock.t += 30
    assert asyncio.run(alerting_service.check_escalations(get_ops_session_factory())) == 0


def test_ack_only_by_owning_driver(client, test_driver, scripted, manager_headers, auth_db):
    from server.app.core.security import create_access_token, hash_password
    from server.app.db.models_auth import User

    post_frame(client, test_driver.id, scripted, 0.30)
    alert_id = close_eyes(client, test_driver.id, scripted, 2.4)["alert_id"]

    other = auth_db.query(User).filter(User.email == "nikhil@nonap.demo").first()
    if other is None:
        other = User(full_name="Nikhil Menon", email="nikhil@nonap.demo",
                     password_hash=hash_password("NoNap@123"), role="driver")
        auth_db.add(other)
        auth_db.commit()
    other_headers = {"Authorization": f"Bearer {create_access_token(user_id=other.id, role='driver')}"}

    assert client.post(f"/api/v1/alerts/{alert_id}/ack", headers=other_headers).status_code == 404
    assert client.post(f"/api/v1/alerts/{alert_id}/ack", headers=manager_headers).status_code == 403
    assert client.get(f"/api/v1/alerts/{alert_id}", headers=other_headers).status_code == 404
    assert client.get(f"/api/v1/alerts/{alert_id}", headers=manager_headers).status_code == 200


def test_heartbeat_online_then_offline(client, test_driver, scripted, driver_headers):
    res = client.post(
        "/api/v1/devices/heartbeat",
        json={"device_id": "pi-hb", "driver_id": test_driver.email, "fps": 2.9,
              "cpu_temp_c": 48.2, "uptime_s": 120, "ip": "192.168.1.50", "camera_backend": "picamera"},
        headers=KEY,
    )
    assert res.status_code == 200
    assert res.json()["device"]["online"] is True

    mine = client.get("/api/v1/driver/device", headers=driver_headers).json()
    assert mine["device"]["device_id"] == "pi-hb" and mine["device"]["online"] is True

    scripted.clock.t += get_settings().DEVICE_OFFLINE_SECONDS + 0.5
    asyncio.run(device_service.check_offline(get_ops_session_factory(), get_auth_session_factory()))
    assert client.get("/api/v1/devices/pi-hb", headers=KEY).json()["online"] is False


def test_ws_role_and_path_enforced(client, driver_token, manager_token, test_driver, test_manager):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/fleet/{test_manager.id}?token={driver_token}") as ws:
            ws.receive_json()
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/driver/{test_manager.id}?token={driver_token}") as ws:
            ws.receive_json()


def test_fleet_ws_receives_alert_event_for_own_driver(client, manager_token, test_manager, test_driver, scripted):
    with client.websocket_connect(f"/ws/fleet/{test_manager.id}?token={manager_token}") as ws:
        assert ws.receive_json()["type"] == "connection_ack"
        assert ws.receive_json()["type"] == "snapshot"
        post_frame(client, test_driver.id, scripted, 0.30)
        close_eyes(client, test_driver.id, scripted, 1.4)
        msg = None
        for _ in range(20):
            m = ws.receive_json()
            if m["type"] == "alert_event":
                msg = m
                break
        assert msg is not None
        assert msg["event"] == "raised" and msg["level"] == 1
        assert msg["driver_id"] == test_driver.id
        assert msg["alert"]["detected_at"].endswith("+05:30")


def test_driver_ws_gets_spoken_level2_message(client, driver_token, test_driver, scripted):
    with client.websocket_connect(f"/ws/driver/{test_driver.id}?token={driver_token}") as ws:
        ws.receive_json()
        ws.receive_json()
        post_frame(client, test_driver.id, scripted, 0.30)
        close_eyes(client, test_driver.id, scripted, 2.4)
        events = []
        for _ in range(40):
            m = ws.receive_json()
            if m["type"] == "alert_event":
                events.append(m)
                if m["level"] == 2:
                    break
        assert [e["event"] for e in events] == ["raised", "upgraded"]
        assert "you seem drowsy" in events[-1]["spoken"].lower()


def test_session_start_end(client, driver_headers):
    started = client.post("/api/v1/driver/session/start", headers=driver_headers).json()
    assert started["active"] is True
    assert client.get("/api/v1/driver/session", headers=driver_headers).json()["active"] is True
    ended = client.post("/api/v1/driver/session/end", headers=driver_headers).json()
    assert ended["active"] is False and ended["ended_at"].endswith("+05:30")
