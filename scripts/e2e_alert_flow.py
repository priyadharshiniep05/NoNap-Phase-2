#!/usr/bin/env python3
"""End-to-end check of the NoNap alerting flow over real HTTP + WebSockets.

It starts the real FastAPI server (temporary databases, seeded demo users) on
a free port, then plays three roles at once:
  * a virtual Pi       - JPEG frames to /api/v1/frames at 3 fps + heartbeats
  * the driver's phone  - /ws/driver/{id} WebSocket + "I'm awake" ack
  * the fleet manager   - /ws/fleet/{id} WebSocket

The only stub is the face model: there is no face in front of a CI machine,
so model_predict returns a scripted EAR (eyes open 0.30 / closed 0.10). Every
other layer (time-window levels, DB2 writes, escalation watchdog, WebSocket
fan-out, device liveness, latency CSV) runs as in production. Use the real
camera and your own eyes for the acceptance test (docs/RUN_GUIDE.md).

    server/.venv/bin/python scripts/e2e_alert_flow.py            # assertions, ~45 s
    server/.venv/bin/python scripts/e2e_alert_flow.py --serve    # keep running for UI demos:
        curl -X POST localhost:8100/__e2e/eyes/closed   (open | closed | yawn | noface | pi_off | pi_on)
"""

import argparse
import asyncio
import json
import os
import socket
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "model"))


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serve", action="store_true", help="keep the server + virtual Pi running for app demos")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 with --serve so a phone can connect")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="nonap_e2e_")
    port = args.port or (8100 if args.serve else free_port())
    os.environ.update({
        "AUTH_DB_URL": "sqlite:///{}/auth.db".format(tmp),
        "OPS_DB_URL": "sqlite:///{}/ops.db".format(tmp),
        "LATENCY_LOG_DIR": os.path.join(tmp, "logs"),
        "VIDEO_SOURCE": "pi",
        "LAPTOP_ALARM_ENABLED": "false",
    })

    import contextlib
    import io as _io

    import cv2
    import numpy as np
    import requests
    import uvicorn
    import websockets

    import server.app.services.detection_service as detection_service
    from server.app.core.config import get_settings
    from server.app.main import app
    from server.scripts.seed_demo import seed_demo_data

    with contextlib.redirect_stdout(_io.StringIO()):
        seed_demo_data()

    # ---- scripted face model ------------------------------------------------
    eyes = {"state": "open", "pi": True}

    def stub_predict(frame=None, driver_id=None, custom_thresholds=None, **_):
        st = eyes["state"]
        ear = 0.10 if st == "closed" else 0.30
        mar = 0.85 if st == "yawn" else 0.15
        face = st != "noface"
        return {
            "driver_id": driver_id, "status": "alert", "face_detected": face,
            "ear": ear if face else 0.0, "mar": mar if face else 0.0,
            "raw_ear": ear if face else 0.0, "raw_mar": mar if face else 0.0,
            "perclos": 0.0, "confidence": 0.9, "backend": "e2e-stub", "latency_ms": 1.0,
        }

    detection_service.model_predict = stub_predict
    detection_service.MODEL_AVAILABLE = True

    @app.post("/__e2e/eyes/{state}", include_in_schema=False)
    def set_eyes(state: str):
        if state in ("pi_off", "pi_on"):
            eyes["pi"] = state == "pi_on"
        else:
            eyes["state"] = state
        return dict(eyes)

    server = uvicorn.Server(uvicorn.Config(app, host=args.host, port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    base = "http://127.0.0.1:{}".format(port)
    for _ in range(100):
        try:
            if requests.get(base + "/health", timeout=0.5).ok:
                break
        except requests.RequestException:
            time.sleep(0.1)

    key = {"X-Device-Key": get_settings().DEVICE_API_KEY}
    pi_log = []
    jpeg = cv2.imencode(".jpg", np.full((240, 320, 3), 90, np.uint8))[1].tobytes()

    def virtual_pi():
        sess = requests.Session()
        last_hb = 0.0
        while True:
            if eyes["pi"]:
                now = time.time()
                if now - last_hb >= 5:
                    last_hb = now
                    try:
                        sess.post(base + "/api/v1/devices/heartbeat", headers=key, timeout=2, json={
                            "device_id": "nonap-pi-01", "driver_id": "driver1@nonap.demo", "fps": 3.0,
                            "cpu_temp_c": 47.5, "ip": "192.168.2.2", "camera_backend": "e2e", "vehicle": "KA 01 AB 4521"})
                    except requests.RequestException:
                        pass
                try:
                    r = sess.post(base + "/api/v1/frames", headers=key, timeout=3,
                                  files={"frame": ("f.jpg", jpeg, "image/jpeg")},
                                  data={"device_id": "nonap-pi-01", "driver_id": "driver1@nonap.demo",
                                        "captured_at": str(int(time.time() * 1000)), "source": "simulated"})
                    pi_log.append((time.time(), r.json()))
                except requests.RequestException:
                    pass
            time.sleep(1 / 3.0)

    threading.Thread(target=virtual_pi, daemon=True).start()

    if args.serve:
        print("NoNap e2e server on http://{}:{}  (VIDEO_SOURCE=pi, scripted eyes, temp DB {})".format(args.host, port, tmp))
        print("Log in as driver1@nonap.demo / manager@nonap.demo with NoNap@123.")
        print("Control:  curl -X POST localhost:{}/__e2e/eyes/closed   # open | closed | yawn | noface | pi_off | pi_on".format(port))
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return 0

    return asyncio.run(run_checks(base, port, eyes, pi_log, tmp))


async def run_checks(base, port, eyes, pi_log, tmp):
    import requests
    import websockets

    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))
        print("  {} {}{}".format("PASS" if ok else "FAIL", name, " - " + detail if detail else ""))

    def login(email):
        r = requests.post(base + "/auth/login", json={"email": email, "password": "NoNap@123"}, timeout=5)
        r.raise_for_status()
        return r.json()

    drv = login("driver1@nonap.demo")
    mgr = login("manager@nonap.demo")
    ws_base = "ws://127.0.0.1:{}".format(port)
    driver_msgs, fleet_msgs = [], []

    async def listen(url, sink):
        async with websockets.connect(url) as ws:
            async for raw in ws:
                m = json.loads(raw)
                m["_rx"] = time.time()
                sink.append(m)
                if m.get("frame_id"):
                    await ws.send(json.dumps({"type": "receipt", "frame_id": m["frame_id"], "received_ms": time.time() * 1000}))

    tasks = [
        asyncio.create_task(listen("{}/ws/driver/{}?token={}".format(ws_base, drv["user_id"], drv["access_token"]), driver_msgs)),
        asyncio.create_task(listen("{}/ws/fleet/{}?token={}".format(ws_base, mgr["user_id"], mgr["access_token"]), fleet_msgs)),
    ]

    async def wait_for(pred, timeout):
        end = time.time() + timeout
        while time.time() < end:
            hit = pred()
            if hit:
                return hit
            await asyncio.sleep(0.05)
        return None

    def events(msgs, event=None, level=None):
        return [m for m in msgs if m.get("type") == "alert_event"
                and (event is None or m["event"] == event) and (level is None or m["level"] == level)]

    def pi_severity_since(t0, sev):
        return next((ts for ts, r in pi_log if ts >= t0 and r.get("severity") == sev), None)

    print("\nNoNap end-to-end alert flow (real HTTP + WebSockets, scripted face model)\n")

    # 1. Awake
    await asyncio.sleep(2.0)
    check("driver WebSocket snapshot", any(m["type"] == "snapshot" for m in driver_msgs))
    check("device online pushed", await wait_for(lambda: any(m["type"] == "device_status" and m["device"]["online"] for m in driver_msgs), 6))
    check("awake frames report severity 0", pi_log and all(r.get("severity") == 0 for _, r in pi_log[-4:]))
    check("live EAR/MAR telemetry reaches the phone", any(m["type"] == "telemetry" and m.get("state") == "awake" for m in driver_msgs))

    # 2. Eyes closed -> L1 -> L2
    t_close = time.time()
    eyes["state"] = "closed"
    l1 = await wait_for(lambda: pi_severity_since(t_close, 1), 3)
    l2 = await wait_for(lambda: pi_severity_since(t_close, 2), 4)
    check("Pi gets level 1 after ~1 s of closed eyes", l1 and 0.9 <= l1 - t_close <= 2.0,
          "{:.2f} s".format(l1 - t_close) if l1 else "never")
    check("Pi gets level 2 after ~2 s of closed eyes", l2 and 1.9 <= l2 - t_close <= 3.0,
          "{:.2f} s".format(l2 - t_close) if l2 else "never")
    up = await wait_for(lambda: events(driver_msgs, "upgraded", 2), 2)
    check("phone receives level 2 with spoken warning",
          up and "you seem drowsy" in up[0].get("spoken", "").lower(), up[0].get("spoken", "") if up else "")
    check("fleet manager sees the alert live", await wait_for(lambda: events(fleet_msgs, "raised"), 2))
    alert_id = up[0]["alert"]["id"] if up else None
    check("one episode = one alert row", len({m["alert"]["id"] for m in events(driver_msgs)}) == 1)

    # 3. "I'm awake" after 1.5 s
    await asyncio.sleep(1.5)
    t_ack = time.time()
    r = requests.post(base + "/api/v1/alerts/{}/ack".format(alert_id),
                      headers={"Authorization": "Bearer " + drv["access_token"]}, timeout=5)
    ack = r.json()
    check("ack recorded with response time", r.ok and ack.get("status") == "acknowledged" and ack.get("response_time_ms"),
          "{} ms".format(ack.get("response_time_ms")))
    stopped = await wait_for(lambda: pi_severity_since(t_ack, 0), 2)
    check("Pi alarm stops within 1 s of the ack", stopped and stopped - t_ack <= 1.0,
          "{:.2f} s".format(stopped - t_ack) if stopped else "never")
    check("fleet sees the acknowledgement", await wait_for(lambda: events(fleet_msgs, "acknowledged"), 2))

    # 4. Ignore the next one -> level 3 after 10 s
    eyes["state"] = "open"
    await asyncio.sleep(2.0)
    t_close2 = time.time()
    eyes["state"] = "closed"
    await wait_for(lambda: pi_severity_since(t_close2, 2), 4)
    eyes["state"] = "open"
    esc = await wait_for(lambda: events(fleet_msgs, "escalated", 3), 14)
    check("unacknowledged level 2 escalates to level 3 on the fleet dashboard",
          esc and esc[0]["alert"]["status"] == "unacknowledged",
          "{:.1f} s after closing".format(esc[0]["_rx"] - t_close2) if esc else "never")
    t3 = await wait_for(lambda: pi_severity_since(esc[0]["_rx"] if esc else time.time(), 3), 2)
    check("Pi shows level 3", t3)
    a3 = esc[0]["alert"]["id"] if esc else None
    requests.post(base + "/api/v1/alerts/{}/ack".format(a3), headers={"Authorization": "Bearer " + drv["access_token"]}, timeout=5)

    # 5. Unplug the Pi -> offline within 15 s
    t_off = time.time()
    eyes["pi"] = False
    off = await wait_for(lambda: next((m for m in driver_msgs if m["type"] == "device_status"
                                        and not m["device"]["online"] and m["_rx"] > t_off), None), 16)
    check("app shows Pi offline within 15 s", off and off["_rx"] - t_off <= 15,
          "{:.1f} s".format(off["_rx"] - t_off) if off else "never")
    eyes["pi"] = True
    back = await wait_for(lambda: next((m for m in driver_msgs if m["type"] == "device_status"
                                         and m["device"]["online"] and m["_rx"] > t_off + 1), None), 8)
    check("Pi recovers automatically", back)

    # 6. Latency CSV
    await asyncio.sleep(0.5)
    import glob
    rows = 0
    with_app = 0
    import csv
    for path in glob.glob(os.path.join(tmp, "logs", "latency_*.csv")):
        with open(path) as f:
            for row in csv.DictReader(f):
                rows += 1
                with_app += bool(row["app_received_ms"])
    check("latency CSV written with app receive times", rows > 0 and with_app > 0, "{} rows, {} with app time".format(rows, with_app))

    for t in tasks:
        t.cancel()
    failed = [n for n, ok, _ in results if not ok]
    print("\n{} / {} checks passed".format(len(results) - len(failed), len(results)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
