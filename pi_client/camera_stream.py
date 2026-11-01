#!/usr/bin/env python3
"""NoNap camera streamer for the Raspberry Pi.

The Pi only captures camera frames and posts them to the backend's
/api/v1/frames. Detection and every alert (sound, vibration, TTS, fleet
notification) happen on the server and in the phone app. Nothing alerts on
the Pi itself.

No packages to install: frames come from `raspivid` (legacy camera stack,
hardware MJPEG encoder) and are posted with the standard library.
Python 3.5-compatible.
Usage:  python3 camera_stream.py [--config config.ini] [--log stream.log]
"""
import configparser
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

LOG_PATH = None


def load_config(path):
    cp = configparser.ConfigParser(inline_comment_prefixes=(";",))
    cp.read(path)

    def get(section, key, default):
        # NONAP_<KEY> environment variables override config.ini
        return os.environ.get("NONAP_" + key.upper(), cp.get(section, key, fallback=default))

    return {
        "server_url": get("server", "server_url", "http://192.168.2.1:8000").rstrip("/"),
        "device_key": get("server", "device_key", "nonap-dev-device-key"),
        "device_id": get("device", "device_id", "nonap-pi-01"),
        "driver_id": get("device", "driver_id", "driver1@nonap.demo"),
        "fps": float(get("camera", "fps", "3")),
        "width": int(get("camera", "width", "320")),
        "height": int(get("camera", "height", "240")),
        "rotation": int(get("camera", "rotation", "0")),
        "hflip": get("camera", "hflip", "false").lower() == "true",
        # Only test tools set this; real Pi frames are always "pi"
        "source": get("device", "source", "pi"),
    }


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S") + "  " + msg
    print(line, flush=True)
    if LOG_PATH:
        try:
            with open(LOG_PATH, "a") as f:
                f.write(line + "\n")
        except OSError:
            pass


class Camera(threading.Thread):
    """Runs raspivid in MJPEG mode and keeps only the newest JPEG frame."""

    def __init__(self, cfg):
        threading.Thread.__init__(self, daemon=True)
        self.cfg = cfg
        self.lock = threading.Lock()
        self.frame = None
        self.frame_at = 0.0
        self.error = None

    def latest(self):
        with self.lock:
            frame, self.frame = self.frame, None
            return frame, self.frame_at

    def run(self):
        c = self.cfg
        cmd = ["raspivid", "-n", "-t", "0", "-cd", "MJPEG", "-w", str(c["width"]), "-h", str(c["height"]),
               "-fps", str(max(int(round(c["fps"])), 1)), "-rot", str(c["rotation"]), "-o", "-"]
        if c["hflip"]:
            cmd.append("-hf")
        while True:
            err_path = "/tmp/nonap_raspivid.err"
            with open(err_path, "wb") as err:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err)
                buf = b""
                while True:
                    chunk = proc.stdout.read1(65536)
                    if not chunk:
                        break
                    buf += chunk
                    while True:
                        start = buf.find(b"\xff\xd8")
                        if start < 0:
                            buf = b""
                            break
                        end = buf.find(b"\xff\xd9", start + 2)
                        if end < 0:
                            buf = buf[start:]
                            break
                        with self.lock:
                            self.frame = buf[start:end + 2]
                            self.frame_at = time.time()
                        buf = buf[end + 2:]
                proc.wait()
            with open(err_path, "rb") as err:
                detail = err.read().decode("utf-8", "replace").strip().splitlines()
            self.error = "raspivid exited (%s): %s" % (proc.returncode, detail[-1] if detail else "no output")
            log("Camera: " + self.error + ". Retrying in 10 s (check the ribbon cable).")
            time.sleep(10)


def post_frame(cfg, jpeg, captured_at, last_rtt):
    boundary = uuid.uuid4().hex
    fields = {"device_id": cfg["device_id"], "driver_id": cfg["driver_id"],
              "captured_at": "%d" % (captured_at * 1000), "source": cfg["source"]}
    if last_rtt is not None:
        fields["last_rtt_ms"] = "%.1f" % last_rtt
    parts = []
    for k, v in fields.items():
        parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (boundary, k, v)).encode())
    parts.append(('--%s\r\nContent-Disposition: form-data; name="frame"; filename="frame.jpg"\r\n'
                  'Content-Type: image/jpeg\r\n\r\n' % boundary).encode())
    parts.append(jpeg)
    parts.append(("\r\n--%s--\r\n" % boundary).encode())
    req = urllib.request.Request(cfg["server_url"] + "/api/v1/frames", data=b"".join(parts), method="POST",
                                 headers={"X-Device-Key": cfg["device_key"],
                                          "Content-Type": "multipart/form-data; boundary=" + boundary})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            r.read()
            return "ok"
    except urllib.error.HTTPError as e:
        return "HTTP %d: %s" % (e.code, e.read()[:120].decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError) as e:
        return "backend unreachable (%s)" % getattr(e, "reason", e)


def main():
    global LOG_PATH
    path = "config.ini"
    if "--config" in sys.argv:
        path = sys.argv[sys.argv.index("--config") + 1]
    if "--log" in sys.argv:
        LOG_PATH = sys.argv[sys.argv.index("--log") + 1]
    cfg = load_config(path)
    period = 1.0 / max(cfg["fps"], 0.2)

    log("Streaming %dx%d @ %.1f fps to %s as %s" % (cfg["width"], cfg["height"], cfg["fps"],
                                                   cfg["server_url"], cfg["device_id"]))
    cam = Camera(cfg)
    cam.start()

    last_rtt = None
    last_status = None
    sent = 0
    while True:
        started = time.time()
        jpeg, captured_at = cam.latest()
        if jpeg is None:
            time.sleep(0.05)
            continue
        status = post_frame(cfg, jpeg, captured_at, last_rtt)
        last_rtt = (time.time() - started) * 1000 if status == "ok" else None
        sent += 1
        if status != last_status:
            log("Backend: " + status)
            last_status = status
        elif sent % 600 == 0:
            log("%d frames sent, last round trip %.0f ms" % (sent, last_rtt or 0))
        if status != "ok":
            time.sleep(2)  # back off while the backend is down or rejecting frames
        wait = period - (time.time() - started)
        if wait > 0:
            time.sleep(wait)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
