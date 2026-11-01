"""Per-frame latency instrumentation for the IEEE paper.

Each processed frame gets a row in logs/latency_<YYYY-MM-DD>.csv (IST date)
with the timestamps that were actually observed. Missing stages stay empty;
nothing is estimated or filled in.

Clock domains (all epoch milliseconds):
  pi_capture_ms       Raspberry Pi clock (or simulate_pi.py / webcam read time)
  server_*_ms         MacBook clock
  app_received_ms     iPhone clock
  pi_rtt_ms           measured entirely on the Pi (send -> response), single clock
Cross-clock differences include the clock offset between devices; keep all
three on NTP and see docs/PAPER_NOTES.md before reporting them.
"""

import csv
import logging
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional

from server.app.core.timezone import ist_wall_now

logger = logging.getLogger("nonap.latency")

COLUMNS = [
    "logged_at_ist",
    "frame_id",
    "source",
    "device_id",
    "driver_id",
    "level",
    "alert_id",
    "pi_capture_ms",
    "server_receive_ms",
    "inference_done_ms",
    "ws_sent_ms",
    "app_received_ms",
    "pi_rtt_ms",
    "inference_ms",
    "server_to_ws_ms",
]

# Rows wait this long for the app's receipt echo before being written without it.
PENDING_TIMEOUT_S = 5.0
MAX_PENDING = 2000


def now_ms() -> float:
    return time.time() * 1000.0


class LatencyLogger:
    def __init__(self, log_dir: str = "logs") -> None:
        self.log_dir = log_dir
        self.enabled = True
        self._pending: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._created: Dict[str, float] = {}
        self._lock = threading.Lock()

    def configure(self, log_dir: str, enabled: bool = True) -> None:
        self.log_dir = log_dir
        self.enabled = enabled

    def start(self, frame_id: str, **fields: Any) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._pending[frame_id] = {"frame_id": frame_id, **fields}
            self._created[frame_id] = time.time()
            while len(self._pending) > MAX_PENDING:
                old_id, row = self._pending.popitem(last=False)
                self._created.pop(old_id, None)
                self._write(row)

    def mark(self, frame_id: Optional[str], **fields: Any) -> None:
        """Record stage timestamps; the first value for a stage wins."""
        if not frame_id or not self.enabled:
            return
        with self._lock:
            row = self._pending.get(frame_id)
            if row is None:
                return
            for k, v in fields.items():
                if row.get(k) in (None, ""):
                    row[k] = v

    def app_received(self, frame_id: str, received_ms: float) -> bool:
        """The app echoed a frame_id it received; finalize that row now."""
        with self._lock:
            row = self._pending.pop(frame_id, None)
            self._created.pop(frame_id, None)
        if row is None:
            return False
        row["app_received_ms"] = received_ms
        self._write(row)
        return True

    def flush_expired(self, now: Optional[float] = None) -> int:
        now = now if now is not None else time.time()
        expired = []
        with self._lock:
            for fid in list(self._pending.keys()):
                if now - self._created.get(fid, now) >= PENDING_TIMEOUT_S:
                    expired.append(self._pending.pop(fid))
                    self._created.pop(fid, None)
                else:
                    break  # insertion-ordered: the rest are newer
        for row in expired:
            self._write(row)
        return len(expired)

    def flush_all(self) -> None:
        with self._lock:
            rows = list(self._pending.values())
            self._pending.clear()
            self._created.clear()
        for row in rows:
            self._write(row)

    def _write(self, row: Dict[str, Any]) -> None:
        # Derived values only from same-clock (server) pairs.
        rx, inf, ws = row.get("server_receive_ms"), row.get("inference_done_ms"), row.get("ws_sent_ms")
        if rx is not None and inf is not None:
            row["inference_ms"] = round(inf - rx, 2)
        if rx is not None and ws is not None:
            row["server_to_ws_ms"] = round(ws - rx, 2)

        wall = ist_wall_now()
        row["logged_at_ist"] = wall.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        path = Path(self.log_dir) / f"latency_{wall.strftime('%Y-%m-%d')}.csv"
        try:
            os.makedirs(path.parent, exist_ok=True)
            new_file = not path.exists()
            with open(path, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
                if new_file:
                    writer.writeheader()
                writer.writerow({k: _fmt(row.get(k)) for k in COLUMNS})
        except OSError as e:
            logger.warning(f"Could not write latency row: {e}")


def _fmt(v: Any) -> Any:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.2f}"
    return v


latency_logger = LatencyLogger()
