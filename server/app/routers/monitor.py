"""Webcam monitoring and video preview stream endpoints.

NOTE: All frames exist purely in volatile memory. No video or frame is ever
persisted to disk, respecting privacy and storage constraints.
"""

import asyncio
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server.app.core.deps import get_current_user
from server.app.db.models_auth import User
from server.app.capture.webcam_worker import webcam_worker

router = APIRouter(prefix="/monitor", tags=["Webcam Monitoring"])


class StartMonitorRequest(BaseModel):
    driver_id: Optional[str] = None
    camera_index: Optional[int] = None


@router.post("/start")
def start_monitoring(
    payload: StartMonitorRequest,
    current_user: User = Depends(get_current_user),
):
    """Start background webcam processing."""
    # If user is a driver, default to their own user id
    target_driver_id = payload.driver_id
    if current_user.role == "driver":
        target_driver_id = current_user.id
    elif not target_driver_id:
        target_driver_id = current_user.id

    webcam_worker.start(
        driver_id=target_driver_id,
        camera_index=payload.camera_index,
    )
    return {
        "status": "started",
        "driver_id": target_driver_id,
        "is_running": webcam_worker.is_running,
    }


@router.post("/stop")
def stop_monitoring(
    current_user: User = Depends(get_current_user),
):
    """Stop background webcam capture."""
    webcam_worker.stop()
    return {
        "status": "stopped",
        "is_running": webcam_worker.is_running,
    }


@router.get("/status")
def get_monitor_status():
    """Get current capture status and FPS telemetry."""
    return {
        "is_running": webcam_worker.is_running,
        "driver_id": webcam_worker.driver_id,
        **webcam_worker.get_stats(),
    }


@router.get("/preview")
def get_preview_frame():
    """Retrieve the latest live frame as a single JPEG image."""
    jpeg_bytes = webcam_worker.get_preview_jpeg()
    if not jpeg_bytes:
        # Fallback 1x1 blank JPEG if not started
        import cv2
        import numpy as np
        blank = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.putText(blank, "No Video", (90, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        _, enc = cv2.imencode(".jpg", blank)
        jpeg_bytes = enc.tobytes()

    return Response(content=jpeg_bytes, media_type="image/jpeg")


@router.get("/stream")
def get_mjpeg_stream():
    """Live MJPEG video stream over HTTP multipart."""

    async def _generator():
        while True:
            jpeg = webcam_worker.get_preview_jpeg()
            if jpeg:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                )
            await asyncio.sleep(0.1)

    return StreamingResponse(
        _generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
