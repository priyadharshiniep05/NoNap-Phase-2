"""Background webcam capture and real-time processing worker.

Frames exist strictly in memory. Never saved to disk.
"""

import asyncio
import logging
import threading
import time
from typing import Optional, Dict, Any

import cv2
import numpy as np

from server.app.core.config import get_settings
from server.app.db.auth_db import get_auth_session_factory
from server.app.db.ops_db import get_ops_session_factory
from server.app.services.detection_service import process_frame

logger = logging.getLogger("nonap.webcam")


class WebcamWorker:
    """Manages continuous webcam capture, inference loop, and live preview buffer."""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._driver_id: Optional[str] = None
        self._latest_jpeg: Optional[bytes] = None
        self._latest_stats: Dict[str, Any] = {
            "fps": 0.0,
            "frames_processed": 0,
            "status": "stopped",
            "driver_id": None,
        }
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def driver_id(self) -> Optional[str]:
        return self._driver_id

    def get_preview_jpeg(self) -> Optional[bytes]:
        """Return the latest annotated/clean JPEG frame bytes in memory."""
        with self._lock:
            return self._latest_jpeg

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._latest_stats)

    def start(self, driver_id: str, camera_index: Optional[int] = None):
        """Start the background webcam capture thread."""
        if self._running:
            logger.info("Webcam worker already running, switching driver_id")
            self._driver_id = driver_id
            with self._lock:
                self._latest_stats["driver_id"] = driver_id
            return

        self._running = True
        self._driver_id = driver_id
        with self._lock:
            self._latest_stats["status"] = "running"
            self._latest_stats["driver_id"] = driver_id
            self._latest_stats["frames_processed"] = 0

        settings = get_settings()
        idx = camera_index if camera_index is not None else settings.WEBCAM_INDEX

        self._thread = threading.Thread(
            target=self._capture_loop,
            args=(idx,),
            daemon=True,
            name="NoNapWebcamWorker",
        )
        self._thread.start()
        logger.info(f"Webcam worker thread started with camera_index={idx}, driver_id={driver_id}")

    def stop(self):
        """Stop background webcam capture."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        with self._lock:
            self._latest_stats["status"] = "stopped"
        logger.info("Webcam worker stopped")

    def _capture_loop(self, camera_index: int):
        settings = get_settings()
        target_fps = settings.WEBCAM_FPS or 10
        frame_interval = 1.0 / target_fps

        cap = None
        use_synthetic = False

        try:
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                logger.warning(f"Could not open camera {camera_index}. Falling back to synthetic frame generator.")
                use_synthetic = True
        except Exception as e:
            logger.warning(f"Camera open failed ({e}). Using synthetic generator.")
            use_synthetic = True

        auth_session_factory = get_auth_session_factory()
        ops_session_factory = get_ops_session_factory()

        frame_count = 0
        fps_start_time = time.time()
        fps_frame_count = 0
        current_fps = 0.0

        # Dedicated async loop for DB/WS calls from this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while self._running:
                t0 = time.time()

                if use_synthetic or cap is None:
                    # Synthetic 640x480 test pattern frame
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(
                        frame,
                        f"NoNap Webcam Stream (Synthetic) | Driver: {self._driver_id}",
                        (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 200),
                        2,
                    )
                    cv2.putText(
                        frame,
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                        (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (180, 180, 180),
                        1,
                    )
                else:
                    ret, frame = cap.read()
                    if not ret:
                        time.sleep(0.05)
                        continue

                frame_count += 1
                fps_frame_count += 1

                # Calculate running FPS
                elapsed = time.time() - fps_start_time
                if elapsed >= 1.0:
                    current_fps = round(fps_frame_count / elapsed, 1)
                    fps_frame_count = 0
                    fps_start_time = time.time()

                # Encode to JPEG for /preview in memory
                success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if success:
                    with self._lock:
                        self._latest_jpeg = encoded.tobytes()

                # Run inference if driver_id assigned
                if self._driver_id:
                    auth_db = auth_session_factory()
                    ops_db = ops_session_factory()
                    try:
                        loop.run_until_complete(
                            process_frame(
                                frame=frame,
                                driver_id=self._driver_id,
                                auth_session=auth_db,
                                ops_session=ops_db,
                                source="webcam",
                                broadcast_telemetry=True,
                            )
                        )
                    except Exception as e:
                        logger.error(f"Error in webcam frame processing: {e}")
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
            loop.close()
            logger.info("Webcam capture loop terminated cleanly.")


# Singleton webcam worker
webcam_worker = WebcamWorker()
