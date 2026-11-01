"""Background webcam / video file capture and real-time processing worker.

Frames exist strictly in memory. Never saved to disk.
Supports:
- Live MacBook webcam (index 0)
- Video file input via --source / video path with seamless looping
- Real-time MediaPipe landmarks and baseline calibration
"""

import asyncio
import logging
import os
import threading
import time
from typing import Optional, Dict, Any, Union

import cv2
import numpy as np

from server.app.core.config import get_settings
from server.app.core.runtime import get_main_loop
from server.app.services.latency_logger import latency_logger, now_ms
from server.app.db.auth_db import get_auth_session_factory
from server.app.db.ops_db import get_ops_session_factory
from server.app.services.detection_service import process_frame

logger = logging.getLogger("nonap.webcam")


class WebcamWorker:
    """Manages continuous webcam/video capture, inference loop, and live preview buffer."""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._driver_id: Optional[str] = None
        self._source: Union[int, str] = 0
        self._mirror: bool = True
        self._latest_jpeg: Optional[bytes] = None
        self._latest_stats: Dict[str, Any] = {
            "fps": 0.0,
            "frames_processed": 0,
            "status": "stopped",
            "driver_id": None,
            "source": 0,
            "mirror": True,
        }
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def driver_id(self) -> Optional[str]:
        return self._driver_id

    @property
    def mirror(self) -> bool:
        return self._mirror

    def set_mirror(self, mirror: bool):
        self._mirror = mirror
        with self._lock:
            self._latest_stats["mirror"] = mirror
        logger.info(f"Camera mirroring set to: {mirror}")

    def get_preview_jpeg(self) -> Optional[bytes]:
        """Return the latest annotated/clean JPEG frame bytes in memory."""
        with self._lock:
            return self._latest_jpeg

    def set_preview_jpeg(self, jpeg: bytes) -> None:
        """Latest frame from another source (the Pi) for /monitor/preview. Memory only."""
        with self._lock:
            self._latest_jpeg = jpeg

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._latest_stats)

    def start(
        self,
        driver_id: str,
        source: Optional[Union[int, str]] = None,
        mirror: Optional[bool] = None,
    ):
        """Start the background webcam or video capture thread.

        Args:
            driver_id: Driver ID to bind real-time processing to.
            source: Webcam device index (int) or path to a test video file (str).
            mirror: Whether to horizontally mirror webcam frames.
        """
        if mirror is not None:
            self._mirror = mirror

        settings = get_settings()
        chosen_source = source if source is not None else settings.WEBCAM_INDEX

        if self._running:
            logger.info("Capture worker already running, switching driver_id and source")
            self._driver_id = driver_id
            self._source = chosen_source
            with self._lock:
                self._latest_stats["driver_id"] = driver_id
                self._latest_stats["source"] = str(chosen_source)
                self._latest_stats["mirror"] = self._mirror
            return

        self._running = True
        self._driver_id = driver_id
        self._source = chosen_source
        with self._lock:
            self._latest_stats["status"] = "running"
            self._latest_stats["driver_id"] = driver_id
            self._latest_stats["source"] = str(chosen_source)
            self._latest_stats["mirror"] = self._mirror
            self._latest_stats["frames_processed"] = 0

        self._thread = threading.Thread(
            target=self._capture_loop,
            args=(chosen_source,),
            daemon=True,
            name="NoNapCaptureWorker",
        )
        self._thread.start()
        logger.info(
            f"Capture worker thread started with source={chosen_source}, "
            f"driver_id={driver_id}, mirror={self._mirror}"
        )

    def stop(self):
        """Stop background capture."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        with self._lock:
            self._latest_stats["status"] = "stopped"
        logger.info("Capture worker stopped")

    def _capture_loop(self, source: Union[int, str]):
        settings = get_settings()
        target_fps = settings.WEBCAM_FPS or 10
        frame_interval = 1.0 / target_fps

        cap = None
        use_synthetic = False
        is_video_file = isinstance(source, str) and not source.isdigit()

        try:
            # Parse source: int index or filepath
            if isinstance(source, str) and source.isdigit():
                cap_src = int(source)
            else:
                cap_src = source

            cap = cv2.VideoCapture(cap_src)
            if not cap.isOpened():
                logger.warning(f"Could not open capture source {source}. Falling back to synthetic pattern.")
                use_synthetic = True
            else:
                logger.info(f"Successfully opened capture source: {source}")
        except Exception as e:
            logger.warning(f"Capture source open failed ({e}). Using synthetic generator.")
            use_synthetic = True

        auth_session_factory = get_auth_session_factory()
        ops_session_factory = get_ops_session_factory()

        frame_count = 0
        fps_start_time = time.time()
        fps_frame_count = 0
        current_fps = 0.0

        # Pipeline coroutines run on the server's main loop, which owns the
        # WebSockets and the level-3 watchdog.
        loop = get_main_loop()
        if loop is None:
            logger.error("Main event loop not registered; webcam worker cannot run.")
            self._running = False
            return

        try:
            while self._running:
                t0 = time.time()

                captured_ms = now_ms()
                if use_synthetic or cap is None:
                    # Synthetic 640x480 test pattern frame
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(
                        frame,
                        f"NoNap Stream (Synthetic) | Driver: {self._driver_id}",
                        (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 200),
                        2,
                    )
                    cv2.putText(
                        frame,
                        time.strftime("%Y-%m-%d %H:%M:%S IST"),
                        (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (180, 180, 180),
                        1,
                    )
                else:
                    ret, frame = cap.read()
                    captured_ms = now_ms()
                    if not ret:
                        if is_video_file:
                            # Loop video file seamlessly
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            ret, frame = cap.read()
                        if not ret:
                            time.sleep(0.05)
                            continue

                # Horizontally mirror webcam frame if mirroring is enabled
                if self._mirror and not is_video_file and frame is not None:
                    frame = cv2.flip(frame, 1)

                frame_count += 1
                fps_frame_count += 1

                # Calculate running FPS
                elapsed = time.time() - fps_start_time
                if elapsed >= 1.0:
                    current_fps = round(fps_frame_count / elapsed, 1)
                    fps_frame_count = 0
                    fps_start_time = time.time()

                # Encode to JPEG for in-memory /preview
                success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if success:
                    with self._lock:
                        self._latest_jpeg = encoded.tobytes()

                # Run inference if driver_id assigned
                if self._driver_id:
                    auth_db = auth_session_factory()
                    ops_db = ops_session_factory()
                    frame_id = f"webcam-{int(captured_ms)}"
                    latency_logger.start(
                        frame_id,
                        source="video" if is_video_file else "webcam",
                        device_id="macbook-webcam",
                        driver_id=self._driver_id,
                        pi_capture_ms=captured_ms,
                        server_receive_ms=captured_ms,
                    )
                    try:
                        asyncio.run_coroutine_threadsafe(
                            process_frame(
                                frame=frame,
                                driver_id=self._driver_id,
                                auth_session=auth_db,
                                ops_session=ops_db,
                                source="webcam",
                                broadcast_telemetry=True,
                                device_id="macbook-webcam",
                                frame_id=frame_id,
                            ),
                            loop,
                        ).result(timeout=10)
                    except Exception as e:
                        logger.error(f"Error in frame processing: {e}")
                    finally:
                        auth_db.close()
                        ops_db.close()

                with self._lock:
                    self._latest_stats["fps"] = current_fps
                    self._latest_stats["frames_processed"] = frame_count

                # Regulate FPS
                dt = time.time() - t0
                sleep_time = frame_interval - dt
                if sleep_time > 0:
                    time.sleep(sleep_time)

        finally:
            if cap:
                cap.release()
            logger.info("Capture loop terminated cleanly.")


# Singleton webcam worker
webcam_worker = WebcamWorker()
