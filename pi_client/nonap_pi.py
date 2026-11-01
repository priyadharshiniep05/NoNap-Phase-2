#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NoNap thin client for Raspberry Pi 1 Model B (+ Pi Camera).

Captures small JPEG frames, POSTs them to the NoNap backend on the MacBook,
and turns the answer into local alerts:
  * on-board green ACT LED patterns
  * chime / alarm through the 3.5 mm audio jack (aplay)
  * one colour-coded status line in the terminal

No ML runs here. Dependencies: requests + the standard library, plus picamera
when available (falls back to raspistill, then rpicam-still/libcamera-still).
Written for Python 3.5+ (no f-strings) so it runs on older Raspberry Pi OS.

Run:  python3 nonap_pi.py [--config config.ini]
"""

from __future__ import print_function

import argparse
import configparser
import glob
import io
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time

try:
    import requests
except ImportError:
    sys.stderr.write("requests is missing. Install it with:  sudo apt install python3-requests\n")
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "2.0"

BANNER = r"""
  _   _       _   _
 | \ | | ___ | \ | | __ _ _ __
 |  \| |/ _ \|  \| |/ _` | '_ \
 | |\  | (_) | |\  | (_| | |_) |
 |_| \_|\___/|_| \_|\__,_| .__/
   Pi camera client v{ver}  |_|
"""


# --------------------------------------------------------------------------
# Terminal output
# --------------------------------------------------------------------------

class Term(object):
    """ANSI colours only when attached to a real terminal (systemd gets plain lines)."""

    def __init__(self):
        self.tty = sys.stdout.isatty()

    def c(self, code, text):
        return "\033[{}m{}\033[0m".format(code, text) if self.tty else text

    def green(self, t):
        return self.c("32", t)

    def amber(self, t):
        return self.c("33", t)

    def red(self, t):
        return self.c("31", t)

    def cyan(self, t):
        return self.c("36", t)

    def dim(self, t):
        return self.c("2", t)

    def bold(self, t):
        return self.c("1", t)

    def log(self, msg):
        stamp = time.strftime("%H:%M:%S")
        if self.tty:
            sys.stdout.write("\r\033[K")
        print("{} {}".format(self.dim(stamp), msg))
        sys.stdout.flush()

    def status(self, text):
        if self.tty:
            sys.stdout.write("\r\033[K" + text)
            sys.stdout.flush()


TERM = Term()


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

def load_config(path):
    cp = configparser.ConfigParser()
    if not cp.read(path):
        TERM.log(TERM.red("Config file not found: {}".format(path)))
        sys.exit(1)

    def get(section, key, fallback=None):
        env = os.environ.get("NONAP_{}".format(key.upper()))
        if env is not None:
            return env
        return cp.get(section, key, fallback=fallback)

    cfg = {
        "server_url": get("server", "server_url", "http://192.168.1.10:8000").rstrip("/"),
        "device_key": get("server", "device_key", "nonap-dev-device-key"),
        "device_id": get("device", "device_id", "nonap-pi-01"),
        "driver_id": get("device", "driver_id", "driver1@nonap.demo"),
        "vehicle": get("device", "vehicle", ""),
        "fps": float(get("camera", "fps", "3")),
        "min_fps": float(get("camera", "min_fps", "0.5")),
        "width": int(get("camera", "width", "320")),
        "height": int(get("camera", "height", "240")),
        "quality": int(get("camera", "jpeg_quality", "70")),
        "rotation": int(get("camera", "rotation", "0")),
        "hflip": get("camera", "hflip", "false").lower() in ("1", "true", "yes"),
        "backend": get("camera", "backend", "auto"),
        "led_enabled": get("alerts", "led_enabled", "true").lower() in ("1", "true", "yes"),
        "sound_enabled": get("alerts", "sound_enabled", "true").lower() in ("1", "true", "yes"),
        "aplay_device": get("alerts", "aplay_device", ""),
        "chime": get("alerts", "chime_wav", os.path.join(HERE, "sounds", "chime.wav")),
        "alarm": get("alerts", "alarm_wav", os.path.join(HERE, "sounds", "alarm.wav")),
        # The project has no buzzer; kept only so old configs do not break.
        "buzzer_enabled": get("alerts", "buzzer_enabled", "false").lower() in ("1", "true", "yes"),
        # "pi" for the real device; tools/simulate_pi.py sends "simulated" so logs stay separate
        "source": get("device", "source", "pi"),
    }
    for key in ("chime", "alarm"):
        if not os.path.isabs(cfg[key]):
            cfg[key] = os.path.join(HERE, cfg[key])
    return cfg


# --------------------------------------------------------------------------
# Shared state
# --------------------------------------------------------------------------

class State(object):
    def __init__(self):
        self.lock = threading.Lock()
        self.connected = False
        self.ever_connected = False
        self.severity = 0
        self.alert_id = None
        self.last_state = "-"
        self.last_latency_ms = None
        self.rtt_avg_ms = None
        self.fps_achieved = 0.0
        self.target_fps = 3.0
        self.frames_sent = 0
        self.dropped = 0
        self.errors = 0
        self.last_error = ""
        self.driver_name = None
        self.stop = threading.Event()

    def snapshot(self):
        with self.lock:
            return dict(self.__dict__)


# --------------------------------------------------------------------------
# ACT LED
# --------------------------------------------------------------------------

class Led(object):
    """Drives the on-board ACT LED from a background thread.

    Patterns: connected = one short blink every 2 s (slow heartbeat)
              backend unreachable = double blink every 2 s
              level 1 = fast blink, level 2-3 = solid on
    """

    def __init__(self, state, enabled=True):
        self.state = state
        self.enabled = enabled
        self.path = None
        self.original_trigger = None
        self.ok = False
        self.thread = None
        if not enabled:
            return
        for name in ("led0", "ACT"):
            p = "/sys/class/leds/{}".format(name)
            if os.path.isdir(p):
                self.path = p
                break
        if self.path is None:
            TERM.log(TERM.amber("ACT LED not found under /sys/class/leds; LED patterns disabled."))
            return
        try:
            with open(os.path.join(self.path, "trigger")) as f:
                text = f.read()
            if "[" in text:
                self.original_trigger = text.split("[", 1)[1].split("]", 1)[0]
            self._write("trigger", "none")
            self.ok = True
        except (IOError, OSError) as e:
            TERM.log(TERM.amber("Cannot control the ACT LED ({}).".format(e)))
            TERM.log("  Fix: run with sudo, or run pi_client/install.sh which adds a udev rule")
            TERM.log("  (/etc/udev/rules.d/99-nonap-led.rules) and then reboot.")

    def _write(self, name, value):
        with open(os.path.join(self.path, name), "w") as f:
            f.write(str(value))

    def _set(self, on):
        try:
            self._write("brightness", 1 if on else 0)
        except (IOError, OSError):
            pass

    def mode(self):
        s = self.state
        with s.lock:
            if not s.connected:
                return "unreachable"
            if s.severity >= 2:
                return "solid"
            if s.severity == 1:
                return "fast"
            return "heartbeat"

    def _sleep(self, seconds, mode):
        """Sleep in small steps; return early if the mode changed."""
        end = time.time() + seconds
        while time.time() < end and not self.state.stop.is_set():
            if self.mode() != mode:
                return False
            time.sleep(0.05)
        return True

    def run(self):
        while not self.state.stop.is_set():
            m = self.mode()
            if m == "solid":
                self._set(True)
                self._sleep(0.3, m)
            elif m == "fast":
                self._set(True)
                if self._sleep(0.1, m):
                    self._set(False)
                    self._sleep(0.1, m)
            elif m == "unreachable":
                for _ in range(2):
                    self._set(True)
                    self._sleep(0.12, m)
                    self._set(False)
                    self._sleep(0.15, m)
                self._sleep(1.6, m)
            else:
                self._set(True)
                if self._sleep(0.15, m):
                    self._set(False)
                    self._sleep(1.85, m)

    def start(self):
        if self.ok:
            self.thread = threading.Thread(target=self.run, name="led")
            self.thread.daemon = True
            self.thread.start()

    def restore(self):
        if not self.ok:
            return
        try:
            self._write("trigger", self.original_trigger or "mmc0")
        except (IOError, OSError):
            pass


# --------------------------------------------------------------------------
# Sound through the 3.5 mm jack
# --------------------------------------------------------------------------

class Sound(object):
    """Non-blocking aplay. Never overlaps: a new sound replaces the old one,
    and the alarm loops until stop() is called."""

    player = "aplay"

    def __init__(self, cfg):
        self.enabled = cfg["sound_enabled"] and shutil.which(self.player) is not None
        self.device = cfg["aplay_device"]
        self.chime = cfg["chime"]
        self.alarm = cfg["alarm"]
        self.proc = None
        self.looping = False
        self.lock = threading.Lock()
        if cfg["sound_enabled"] and not self.enabled:
            TERM.log(TERM.amber("{} not found (sudo apt install alsa-utils); sounds disabled.".format(self.player)))
        for p in (self.chime, self.alarm):
            if self.enabled and not os.path.exists(p):
                TERM.log(TERM.amber("Missing {} - run: python3 tools/make_sounds.py".format(p)))

    def command(self, path):
        cmd = ["aplay", "-q"]
        if self.device:
            cmd += ["-D", self.device]
        return cmd + [path]

    def _play(self, path):
        cmd = self.command(path)
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            TERM.log(TERM.amber("aplay failed: {}".format(e)))
            self.proc = None

    def _busy(self):
        return self.proc is not None and self.proc.poll() is None

    def play_chime(self):
        if not self.enabled:
            return
        with self.lock:
            if self.looping or self._busy():
                return  # alarm (or a chime) already playing
            self._play(self.chime)

    def start_alarm(self):
        if not self.enabled:
            return
        with self.lock:
            if self.looping:
                return
            self._kill()
            self.looping = True
            self._play(self.alarm)

    def tick(self):
        """Restart the alarm when one pass finishes (called often by the main loop)."""
        with self.lock:
            if self.looping and not self._busy():
                self._play(self.alarm)

    def stop(self):
        with self.lock:
            self.looping = False
            self._kill()

    def _kill(self):
        if self._busy():
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.proc = None


# --------------------------------------------------------------------------
# Camera backends
# --------------------------------------------------------------------------

class PiCameraSource(object):
    name = "picamera"

    def __init__(self, cfg):
        import picamera  # noqa: F401  (raises ImportError when unavailable)
        self.cam = picamera.PiCamera()
        self.cam.resolution = (cfg["width"], cfg["height"])
        self.cam.framerate = max(1, int(round(cfg["fps"] * 2)))
        self.cam.rotation = cfg["rotation"]
        self.cam.hflip = cfg["hflip"]
        self.quality = cfg["quality"]
        self.stream = io.BytesIO()
        time.sleep(2.0)  # sensor auto-exposure warm-up
        self.frames = self.cam.capture_continuous(
            self.stream, format="jpeg", use_video_port=True, quality=self.quality
        )

    def read(self):
        next(self.frames)
        captured_ms = time.time() * 1000.0
        data = self.stream.getvalue()
        self.stream.seek(0)
        self.stream.truncate()
        return data, captured_ms

    def close(self):
        try:
            self.cam.close()
        except Exception:
            pass


class StillsCommandSource(object):
    """raspistill / rpicam-still / libcamera-still in timelapse mode writing to
    RAM (/dev/shm), so the camera is opened once instead of per frame."""

    def __init__(self, cfg, command):
        self.name = command
        self.dir = "/dev/shm/nonap" if os.path.isdir("/dev/shm") else "/tmp/nonap"
        if os.path.isdir(self.dir):
            shutil.rmtree(self.dir, ignore_errors=True)
        os.makedirs(self.dir)
        interval_ms = int(1000.0 / max(cfg["fps"], 0.5))
        pattern = os.path.join(self.dir, "f%06d.jpg")
        if command == "raspistill":
            args = [command, "-n", "-t", "0", "-tl", str(interval_ms),
                    "-w", str(cfg["width"]), "-h", str(cfg["height"]),
                    "-q", str(cfg["quality"]), "-rot", str(cfg["rotation"]), "-o", pattern]
            if cfg["hflip"]:
                args.append("-hf")
        else:  # rpicam-still / libcamera-still (Bookworm and later)
            args = [command, "-n", "-t", "0", "--timelapse", str(interval_ms),
                    "--width", str(cfg["width"]), "--height", str(cfg["height"]),
                    "-q", str(cfg["quality"]), "--rotation", str(cfg["rotation"]), "-o", pattern]
            if cfg["hflip"]:
                args.append("--hflip")
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.last = None
        time.sleep(1.0)
        if self.proc.poll() is not None:
            err = self.proc.stderr.read().decode("utf-8", "replace").strip()
            raise RuntimeError("{} exited: {}".format(command, err[-300:]))

    def read(self):
        deadline = time.time() + 5.0
        while time.time() < deadline:
            files = sorted(glob.glob(os.path.join(self.dir, "f*.jpg")))
            # The newest file may still be being written: take the one before it.
            if len(files) >= 2 and files[-2] != self.last:
                path = files[-2]
                for old in files[:-2]:
                    _remove(old)
                with open(path, "rb") as f:
                    data = f.read()
                captured_ms = os.path.getmtime(path) * 1000.0
                self.last = path
                _remove(path)
                return data, captured_ms
            if self.proc.poll() is not None:
                raise RuntimeError("{} stopped unexpectedly".format(self.name))
            time.sleep(0.03)
        raise RuntimeError("No frame from {} in 5 s".format(self.name))

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except Exception:
                self.proc.kill()
        shutil.rmtree(self.dir, ignore_errors=True)


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def open_camera(cfg):
    """Detect the available camera stack: picamera, then raspistill, then rpicam-still."""
    wanted = cfg["backend"]
    errors = []
    if wanted in ("auto", "picamera"):
        try:
            return PiCameraSource(cfg)
        except Exception as e:
            errors.append("picamera: {}".format(e))
    for cmd in ("raspistill", "rpicam-still", "libcamera-still"):
        if wanted not in ("auto", cmd):
            continue
        if shutil.which(cmd):
            try:
                return StillsCommandSource(cfg, cmd)
            except Exception as e:
                errors.append("{}: {}".format(cmd, e))
        else:
            errors.append("{}: not installed".format(cmd))
    TERM.log(TERM.red("No working camera backend:"))
    for e in errors:
        TERM.log("  - " + e)
    TERM.log("Check the ribbon cable (blue side towards the Ethernet port) and that the camera")
    TERM.log("is enabled: sudo raspi-config -> Interface Options -> Legacy Camera -> Yes, then reboot.")
    TERM.log("Test with:  raspistill -o test.jpg")
    sys.exit(2)


# --------------------------------------------------------------------------
# System info for heartbeats
# --------------------------------------------------------------------------

def cpu_temp_c():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except (IOError, OSError, ValueError):
        return None


def uptime_s():
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except (IOError, OSError, ValueError, IndexError):
        return None


def local_ip(server_url):
    host = server_url.split("://", 1)[-1].split("/", 1)[0].split(":")[0]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, 9))  # UDP: no packet is sent, just picks the outgoing interface
        return s.getsockname()[0]
    except (socket.error, OSError):
        return None
    finally:
        s.close()


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------

class Client(object):
    sound_class = Sound
    CONNECT_TIMEOUT = 2.0
    READ_TIMEOUT = 5.0

    def __init__(self, cfg):
        self.cfg = cfg
        self.state = State()
        self.state.target_fps = cfg["fps"]
        self.session = requests.Session()
        self.session.headers.update({"X-Device-Key": cfg["device_key"], "User-Agent": "nonap-pi/" + VERSION})
        self.led = Led(self.state, cfg["led_enabled"])
        self.sound = self.sound_class(cfg)
        self.camera = None
        self.backoff = 0.5
        self._rtts = []
        self._fps_times = []
        self._last_status = 0
        self.acked_ids = set()

    def open_camera(self, cfg):
        return open_camera(cfg)

    # --- networking ---

    def _url(self, path):
        return self.cfg["server_url"] + path

    def _mark_connected(self, ok, error=""):
        s = self.state
        changed = False
        with s.lock:
            if s.connected != ok:
                changed = True
            s.connected = ok
            if ok:
                s.ever_connected = True
            else:
                s.errors += 1
                s.last_error = error
                s.severity = 0
                s.alert_id = None
        if changed:
            if ok:
                TERM.log(TERM.green("Connected to backend at {}".format(self.cfg["server_url"])))
            else:
                TERM.log(TERM.red("Backend unreachable: {}".format(error)))
                self.sound.stop()  # state unknown without the server: do not ring forever

    def send_frame(self, jpeg, captured_ms):
        data = {
            "device_id": self.cfg["device_id"],
            "driver_id": self.cfg["driver_id"],
            "captured_at": "{:.0f}".format(captured_ms),
        }
        if self.cfg.get("source", "pi") != "pi":
            data["source"] = self.cfg["source"]
        if self._rtts:
            data["last_rtt_ms"] = "{:.1f}".format(self._rtts[-1])
        t0 = time.time()
        resp = self.session.post(
            self._url("/api/v1/frames"),
            files={"frame": ("frame.jpg", jpeg, "image/jpeg")},
            data=data,
            timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT),
        )
        rtt_ms = (time.time() - t0) * 1000.0
        if resp.status_code == 401:
            raise RuntimeError("401: device_key in config.ini does not match DEVICE_API_KEY on the server")
        if resp.status_code == 404:
            raise RuntimeError("404: driver '{}' not found on the server".format(self.cfg["driver_id"]))
        if resp.status_code == 409:
            raise RuntimeError("409: server is in webcam mode; restart it with VIDEO_SOURCE=pi")
        resp.raise_for_status()
        self._rtts = (self._rtts + [rtt_ms])[-20:]
        with self.state.lock:
            self.state.rtt_avg_ms = sum(self._rtts) / len(self._rtts)
        return resp.json(), rtt_ms

    def heartbeat_loop(self):
        while not self.state.stop.is_set():
            payload = {
                "device_id": self.cfg["device_id"],
                "driver_id": self.cfg["driver_id"],
                "fps": round(self.state.fps_achieved, 2),
                "cpu_temp_c": cpu_temp_c(),
                "uptime_s": uptime_s(),
                "ip": local_ip(self.cfg["server_url"]),
                "camera_backend": self.camera.name if self.camera else None,
                "vehicle": self.cfg["vehicle"] or None,
                "rtt_ms": round(self.state.rtt_avg_ms, 1) if self.state.rtt_avg_ms else None,
            }
            try:
                r = self.session.post(self._url("/api/v1/devices/heartbeat"), json=payload,
                                      timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT))
                r.raise_for_status()
                body = r.json()
                with self.state.lock:
                    self.state.driver_name = body.get("driver_name")
                self._mark_connected(True)
            except Exception as e:
                self._mark_connected(False, _short(e))
            self.state.stop.wait(5.0)

    def ack_poll_loop(self):
        """While an alert is active, poll it every second so the alarm stops within ~1 s of "I'm awake"."""
        while not self.state.stop.is_set():
            with self.state.lock:
                alert_id = self.state.alert_id
                connected = self.state.connected
            if alert_id and connected:
                try:
                    r = self.session.get(self._url("/api/v1/alerts/{}".format(alert_id)),
                                         timeout=(self.CONNECT_TIMEOUT, 3.0))
                    if r.ok and r.json().get("status") in ("acknowledged", "resolved"):
                        self.acked_ids.add(alert_id)
                        self.apply(0, None, "awake")
                        TERM.log(TERM.green("Alert acknowledged on the phone - alarm stopped."))
                except Exception:
                    pass
            self.state.stop.wait(1.0)

    # --- alerts ---

    def apply(self, severity, alert_id, state_name):
        if alert_id and alert_id in self.acked_ids:
            # A frame answered just before the tap on the phone: do not re-ring.
            severity, alert_id = 0, None
        s = self.state
        with s.lock:
            prev = s.severity
            prev_id = s.alert_id
            s.severity = severity
            s.alert_id = alert_id
            if state_name:
                s.last_state = state_name
        if severity >= 2:
            if prev < 2:
                TERM.log(TERM.red("LEVEL {} ALERT - alarm on (alert {})".format(severity, alert_id)))
            self.sound.start_alarm()
        elif severity == 1:
            if prev != 1 or alert_id != prev_id:
                TERM.log(TERM.amber("Level 1 alert - chime"))
                self.sound.stop()
                self.sound.play_chime()
        else:
            if prev >= 1:
                self.sound.stop()

    # --- main loop ---

    def adapt_fps(self, rtt_ms):
        """Lower the frame rate when the server is slow, recover when it is fast again."""
        s = self.state
        target = self.cfg["fps"]
        with s.lock:
            current = s.target_fps
            period_ms = 1000.0 / current
            if rtt_ms > 0.9 * period_ms:
                current = max(self.cfg["min_fps"], current * 0.8)
            elif rtt_ms < 0.5 * period_ms and current < target:
                current = min(target, current * 1.1)
            s.target_fps = current

    def tick_fps(self):
        now = time.time()
        self._fps_times = [t for t in self._fps_times if now - t < 5.0] + [now]
        if len(self._fps_times) >= 2:
            span = self._fps_times[-1] - self._fps_times[0]
            with self.state.lock:
                self.state.fps_achieved = (len(self._fps_times) - 1) / span if span > 0 else 0.0

    def print_status(self, force=False):
        now = time.time()
        if not force and now - self._last_status < 0.25:
            return
        self._last_status = now
        s = self.state.snapshot()
        conn = TERM.green("[online] ") if s["connected"] else TERM.red("[offline]")
        sev = s["severity"]
        st = s["last_state"]
        if sev >= 2:
            st_txt = TERM.red("L{} {}".format(sev, st.upper()))
        elif sev == 1:
            st_txt = TERM.amber("L1 {}".format(st))
        elif st == "awake":
            st_txt = TERM.green(st)
        else:
            st_txt = TERM.cyan(st)
        lat = "{:.0f} ms".format(s["last_latency_ms"]) if s["last_latency_ms"] else "-"
        line = "{}  {}  fps {:.1f}/{:.1f}  state {}  latency {}  frames {}  drop {}".format(
            TERM.bold("NoNap"), conn, s["fps_achieved"], s["target_fps"], st_txt, lat,
            s["frames_sent"], s["dropped"])
        if TERM.tty:
            TERM.status(line)
        elif now - getattr(self, "_last_plain", 0) > 30:
            self._last_plain = now  # systemd journal: one summary line every 30 s
            print(line)
            sys.stdout.flush()

    def run(self):
        print(TERM.cyan(BANNER.format(ver=VERSION)))
        TERM.log("Server  {}".format(self.cfg["server_url"]))
        TERM.log("Device  {}   Driver {}".format(self.cfg["device_id"], self.cfg["driver_id"]))
        if self.cfg["buzzer_enabled"]:
            TERM.log(TERM.amber("buzzer_enabled is set but this build has no buzzer support; ignoring."))

        self.camera = self.open_camera(self.cfg)
        TERM.log(TERM.green("Camera ready via {} ({}x{}, q{}, {} fps target)".format(
            self.camera.name, self.cfg["width"], self.cfg["height"], self.cfg["quality"], self.cfg["fps"])))
        self.led.start()
        for target, name in ((self.heartbeat_loop, "heartbeat"), (self.ack_poll_loop, "ack-poll")):
            t = threading.Thread(target=target, name=name)
            t.daemon = True
            t.start()

        while not self.state.stop.is_set():
            loop_start = time.time()
            try:
                jpeg, captured_ms = self.camera.read()
            except Exception as e:
                TERM.log(TERM.red("Camera read failed: {}".format(_short(e))))
                self.state.stop.wait(1.0)
                continue

            try:
                body, rtt_ms = self.send_frame(jpeg, captured_ms)
                self._mark_connected(True)
                self.backoff = 0.5
                with self.state.lock:
                    self.state.frames_sent += 1
                    self.state.last_latency_ms = rtt_ms
                    if body.get("dropped"):
                        self.state.dropped += 1
                self.tick_fps()
                self.adapt_fps(rtt_ms)
                if body.get("error"):
                    TERM.log(TERM.amber("Server: {}".format(body["error"])))
                self.apply(int(body.get("severity") or 0), body.get("alert_id"),
                           body.get("state") or self.state.last_state)
            except Exception as e:
                self._mark_connected(False, _short(e))
                self.print_status(force=True)
                self.state.stop.wait(self.backoff)
                self.backoff = min(self.backoff * 2, 10.0)  # exponential backoff, capped
                continue

            self.sound.tick()
            self.print_status()
            period = 1.0 / max(self.state.target_fps, 0.1)
            remaining = period - (time.time() - loop_start)
            if remaining > 0:
                self.state.stop.wait(remaining)

    def shutdown(self):
        self.state.stop.set()
        self.sound.stop()
        self.led.restore()
        if self.camera is not None:
            self.camera.close()
        if TERM.tty:
            sys.stdout.write("\n")
        TERM.log("NoNap Pi client stopped." + (" LED trigger restored." if self.led.ok else ""))


def _short(e):
    text = str(e)
    if "Max retries exceeded" in text or "Connection refused" in text or "NewConnectionError" in text:
        return "cannot connect"
    if "timed out" in text.lower():
        return "timeout"
    return text[:120]


def main():
    ap = argparse.ArgumentParser(description="NoNap Raspberry Pi camera client")
    ap.add_argument("--config", default=os.path.join(HERE, "config.ini"))
    args = ap.parse_args()

    client = Client(load_config(args.config))

    def _stop(signum, frame):
        client.state.stop.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    try:
        client.run()
    finally:
        client.shutdown()


if __name__ == "__main__":
    main()
