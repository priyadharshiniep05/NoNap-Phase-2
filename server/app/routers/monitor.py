"""Webcam monitoring and video preview stream endpoints.

NOTE: All frames exist purely in volatile memory. No video or frame is ever
persisted to disk, respecting privacy and storage constraints.
"""

import asyncio
from typing import Optional, Union
from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server.app.core.config import get_settings
from server.app.core.deps import get_current_user
from server.app.db.models_auth import User
from server.app.capture.webcam_worker import webcam_worker

router = APIRouter(prefix="/monitor", tags=["Webcam Monitoring"])


class StartMonitorRequest(BaseModel):
    driver_id: Optional[str] = None
    camera_index: Optional[int] = None
    source: Optional[Union[int, str]] = None  # 0 for webcam, or path to video file
    mirror: Optional[bool] = True


class SetMirrorRequest(BaseModel):
    mirror: bool = True


@router.post("/start")
def start_monitoring(
    payload: StartMonitorRequest,
    current_user: User = Depends(get_current_user),
):
    """Start background webcam or video file processing."""
    target_driver_id = payload.driver_id
    if current_user.role == "driver":
        target_driver_id = current_user.id
    elif not target_driver_id:
        target_driver_id = current_user.id

    if get_settings().VIDEO_SOURCE == "pi":
        # Frames come from the Raspberry Pi via /api/v1/frames; the webcam stays off.
        return {
            "status": "pi_mode",
            "driver_id": target_driver_id,
            "source": "pi",
            "mirror": webcam_worker.mirror,
            "is_running": False,
        }

    # Choose source: payload.source > payload.camera_index > 0
    chosen_source = payload.source if payload.source is not None else payload.camera_index

    webcam_worker.start(
        driver_id=target_driver_id,
        source=chosen_source,
        mirror=payload.mirror,
    )
    return {
        "status": "started",
        "driver_id": target_driver_id,
        "source": str(chosen_source or 0),
        "mirror": webcam_worker.mirror,
        "is_running": webcam_worker.is_running,
    }


@router.post("/mirror")
def toggle_mirror(payload: SetMirrorRequest):
    """Toggle horizontal mirroring on the fly."""
    webcam_worker.set_mirror(payload.mirror)
    return {
        "status": "ok",
        "mirror": webcam_worker.mirror,
    }


@router.post("/stop")
def stop_monitoring(
    current_user: User = Depends(get_current_user),
):
    """Stop background capture."""
    webcam_worker.stop()
    return {
        "status": "stopped",
        "is_running": webcam_worker.is_running,
    }


@router.get("/status")
def get_monitor_status():
    """Get current capture status, source, and FPS telemetry."""
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
        import cv2
        import numpy as np
        blank = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.putText(blank, "No Video", (90, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        _, enc = cv2.imencode(".jpg", blank)
        jpeg_bytes = enc.tobytes()

    return Response(content=jpeg_bytes, media_type="image/jpeg")


@router.get("/preview.mjpg")
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
