#!/usr/bin/env python3
"""Pretend to be the Raspberry Pi: send MacBook webcam (or video file) frames
to /api/v1/frames exactly like pi_client/nonap_pi.py does.

It runs the Pi client's own code (same Client class, frame protocol,
heartbeats, adaptive fps, ack polling, alarm logic). Only the camera
(OpenCV instead of picamera) and the speaker (afplay instead of aplay)
change. The LED part is skipped on a Mac.

Requires the backend running with VIDEO_SOURCE=pi. From the repo root:

    model/.venv/bin/python tools/simulate_pi.py                          # webcam 0
    model/.venv/bin/python tools/simulate_pi.py --video clip.mp4         # loop a video file
    model/.venv/bin/python tools/simulate_pi.py --server http://192.168.1.10:8000 --driver driver1@nonap.demo

Frames are tagged source=simulated, so the latency CSV keeps them apart from real Pi data.
"""

import argparse
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pi_client"))

import cv2  # noqa: E402

import nonap_pi  # noqa: E402


class OpenCVSource(object):
    def __init__(self, cfg, source, mirror):
        self.name = "opencv-video" if isinstance(source, str) else "opencv-webcam"
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            nonap_pi.TERM.log(nonap_pi.TERM.red("Cannot open {}. On macOS allow camera access for your terminal "
                                                "(System Settings > Privacy & Security > Camera).".format(source)))
            sys.exit(2)
        self.loop = isinstance(source, str)
        self.mirror = mirror and not self.loop
        self.size = (cfg["width"], cfg["height"])
        self.quality = cfg["quality"]
        self.fps = cfg["fps"]
        self._next = 0.0

    def read(self):
        if self.loop:  # pace video files at the target rate instead of decoding as fast as possible
            wait = self._next - time.time()
            if wait > 0:
                time.sleep(wait)
            self._next = time.time() + 1.0 / max(self.fps, 0.1)
        ok, frame = self.cap.read()
        if not ok and self.loop:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError("no frame from camera")
        captured_ms = time.time() * 1000.0
        if self.mirror:
            frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, self.size, interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
        return buf.tobytes(), captured_ms

    def close(self):
        self.cap.release()


class MacSound(nonap_pi.Sound):
    """The Pi's alarm logic, played through the Mac speaker."""

    player = "afplay"

    def command(self, path):
        return ["afplay", path]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", default=os.environ.get("NONAP_SERVER_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--key", default=os.environ.get("NONAP_DEVICE_KEY", "nonap-dev-device-key"))
    ap.add_argument("--driver", default="driver1@nonap.demo", help="driver email or id")
    ap.add_argument("--device-id", default="sim-pi-01")
    ap.add_argument("--vehicle", default="KA 01 AB 4521 (sim)")
    ap.add_argument("--camera", type=int, default=0, help="webcam index")
    ap.add_argument("--video", help="video file to loop instead of the webcam")
    ap.add_argument("--fps", type=float, default=3.0)
    ap.add_argument("--no-mirror", action="store_true")
    ap.add_argument("--mute", action="store_true", help="do not play the chime/alarm on the Mac")
    args = ap.parse_args()

    cfg = {
        "server_url": args.server.rstrip("/"),
        "device_key": args.key,
        "device_id": args.device_id,
        "driver_id": args.driver,
        "vehicle": args.vehicle,
        "fps": args.fps,
        "min_fps": 0.5,
        "width": 320,
        "height": 240,
        "quality": 70,
        "rotation": 0,
        "hflip": False,
        "backend": "opencv",
        "led_enabled": False,
        "sound_enabled": not args.mute and shutil.which("afplay") is not None,
        "aplay_device": "",
        "chime": os.path.join(ROOT, "pi_client", "sounds", "chime.wav"),
        "alarm": os.path.join(ROOT, "pi_client", "sounds", "alarm.wav"),
        "buzzer_enabled": False,
        "source": "simulated",
    }
    source = args.video if args.video else args.camera

    class SimClient(nonap_pi.Client):
        sound_class = MacSound

        def open_camera(self, c):
            return OpenCVSource(c, source, mirror=not args.no_mirror)

    client = SimClient(cfg)
    import signal

    signal.signal(signal.SIGINT, lambda *_: client.state.stop.set())
    signal.signal(signal.SIGTERM, lambda *_: client.state.stop.set())
    try:
        client.run()
    finally:
        client.shutdown()


if __name__ == "__main__":
    main()
