"""Frame ingest and inference router for thin clients (e.g. Raspberry Pi)."""

import time
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server.app.db.auth_db import get_auth_session
from server.app.db.ops_db import get_ops_session
from server.app.services.detection_service import process_frame, decode_base64_frame
from server.app.schemas.detection import DetectFrameRequest, DetectionResultResponse

router = APIRouter(prefix="/detect", tags=["Detection Ingest"])


@router.post("/frame", response_model=DetectionResultResponse)
async def ingest_frame(
    payload: DetectFrameRequest,
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    """Process a single frame from an edge device (e.g. Raspberry Pi camera)."""
    if payload.frame_b64:
        frame = decode_base64_frame(payload.frame_b64)
        if frame is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to decode base64 frame image.",
            )
    else:
        # Synthetic test frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

    res = await process_frame(
        frame=frame,
        driver_id=payload.driver_id,
        auth_session=auth_db,
        ops_session=ops_db,
        source=payload.source,
        broadcast_telemetry=True,
    )

    return DetectionResultResponse(
        driver_id=payload.driver_id,
        status=res.get("status", "alert"),
        severity=res.get("severity", "low"),
        confidence=res.get("confidence", 0.9),
        ear=res.get("ear", 0.28),
        mar=res.get("mar", 0.15),
        perclos=res.get("perclos", 0.0),
        eyes_closed_seconds=res.get("eyes_closed_seconds", 0.0),
        alert_triggered=res.get("alert_triggered", False),
        alert_type=res.get("alert_type"),
        alert_message=res.get("alert_message"),
        timestamp=res.get("timestamp", time.time()),
        backend=res.get("backend", "baseline"),
    )
