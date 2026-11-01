"""YOLOv8 face and facial ROI localizer for NoNap hybrid pipeline.

Localizes the face bounding box and extracts:
- Eye region of interest (upper ~45% of face box)
- Mouth region of interest (lower ~40% of face box)
"""

import os
from typing import Dict, Optional, Tuple
import cv2
import numpy as np


class FaceROILocalizer:
    """Detects face bounding box and crops Eye/Mouth ROIs using YOLOv8 or fallback."""

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model = None
        self.backend_name = "yolov8"

        # Check for provided or standard checkpoint paths
        paths_to_check = [
            model_path,
            os.path.join(os.path.dirname(__file__), "..", "checkpoints", "yolov8n-face.pt"),
            os.path.join(os.path.dirname(__file__), "..", "weights", "yolov8n.pt"),
            "yolov8n.pt",
        ]
        valid_path = next((p for p in paths_to_check if p and os.path.exists(p)), None)

        if valid_path:
            try:
                from ultralytics import YOLO
                self.model = YOLO(valid_path)
            except Exception as e:
                # If YOLO fails to load, gracefully remain None
                self.model = None

    def localize_rois(
        self, frame_bgr: np.ndarray, fallback_bbox: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[Dict[str, any]]:
        """Extract face bounding box, eye ROI, and mouth ROI from input frame.

        Args:
            frame_bgr: BGR input image.
            fallback_bbox: Optional (xmin, ymin, xmax, ymax) from MediaPipe if available.

        Returns:
            Dictionary with face_bbox, eye_roi, mouth_roi, and cropped images,
            or None if no face is found.
        """
        h, w, _ = frame_bgr.shape
        face_bbox = None

        if self.model is not None:
            try:
                results = self.model(frame_bgr, verbose=False)
                if results and len(results[0].boxes) > 0:
                    box = results[0].boxes[0].xyxy[0].cpu().numpy()
                    face_bbox = (
                        max(0, int(box[0])),
                        max(0, int(box[1])),
                        min(w, int(box[2])),
                        min(h, int(box[3])),
                    )
            except Exception:
                face_bbox = None

        if face_bbox is None and fallback_bbox is not None:
            face_bbox = fallback_bbox

        if face_bbox is None:
            return None

        fx1, fy1, fx2, fy2 = face_bbox
        face_h = fy2 - fy1
        face_w = fx2 - fx1

        if face_h <= 10 or face_w <= 10:
            return None

        # Eye ROI: upper 45% of face bounding box
        eye_y1 = fy1
        eye_y2 = min(fy2, fy1 + int(face_h * 0.45))
        eye_roi = (fx1, eye_y1, fx2, eye_y2)
        eye_crop = frame_bgr[eye_y1:eye_y2, fx1:fx2]

        # Mouth ROI: lower 40% of face bounding box
        mouth_y1 = max(fy1, fy2 - int(face_h * 0.40))
        mouth_y2 = fy2
        mouth_roi = (fx1, mouth_y1, fx2, mouth_y2)
        mouth_crop = frame_bgr[mouth_y1:mouth_y2, fx1:fx2]

        return {
            "face_bbox": face_bbox,
            "eye_roi": eye_roi,
            "mouth_roi": mouth_roi,
            "eye_crop": eye_crop,
            "mouth_crop": mouth_crop,
        }
