"""MediaPipe FaceMesh baseline landmark extraction for EAR and MAR.

Extracts real-time eye aspect ratio (EAR) and mouth aspect ratio (MAR) from 468 face landmarks,
with a 5-frame moving average to smooth sensor noise while maintaining low latency.
"""

from collections import deque
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
import mediapipe as mp


# Landmark indices for Left and Right eyes in MediaPipe Face Mesh (6 points each)
# Left eye: [p1: outer, p2: top1, p3: top2, p4: inner, p5: bottom2, p6: bottom1]
LEFT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
# Right eye: [p1: outer, p2: top1, p3: top2, p4: inner, p5: bottom2, p6: bottom1]
RIGHT_EYE_INDICES = [33, 160, 158, 133, 153, 144]

# Inner lip indices for Mouth Aspect Ratio (MAR):
# p1 = 78 (left corner), p5 = 308 (right corner)
# Top inner lip: p2 = 82, p3 = 13, p4 = 312
# Bottom inner lip: p8 = 87, p7 = 14, p6 = 317
MOUTH_CORNER_LEFT = 78
MOUTH_CORNER_RIGHT = 308
MOUTH_INNER_PAIRS = [(82, 87), (13, 14), (312, 317)]


def _euclidean_distance(p1: np.ndarray, p2: np.ndarray) -> float:
    """Compute Euclidean distance between two 2D points."""
    return float(np.linalg.norm(p1 - p2))


def calculate_ear(eye_points: np.ndarray) -> float:
    """Calculate the Eye Aspect Ratio (EAR) for 6 ordered landmark points.

    EAR = (||p2 - p6|| + ||p3 - p5||) / (2.0 * ||p1 - p4||)
    """
    if len(eye_points) < 6:
        return 0.0

    # Vertical distances (p2-p6 and p3-p5)
    v1 = _euclidean_distance(eye_points[1], eye_points[5])
    v2 = _euclidean_distance(eye_points[2], eye_points[4])
    # Horizontal distance (p1-p4)
    h = _euclidean_distance(eye_points[0], eye_points[3])

    if h <= 1e-6:
        return 0.0
    return (v1 + v2) / (2.0 * h)


def calculate_mar(
    corner_left: np.ndarray,
    corner_right: np.ndarray,
    vertical_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> float:
    """Calculate Mouth Aspect Ratio (MAR) using inner lip landmarks.

    MAR = (||p2 - p8|| + ||p3 - p7|| + ||p4 - p6||) / (2.0 * ||p1 - p5||)
    """
    h = _euclidean_distance(corner_left, corner_right)
    if h <= 1e-6:
        return 0.0

    v_sum = sum(_euclidean_distance(top, bottom) for top, bottom in vertical_pairs)
    return v_sum / (2.0 * h)


class LandmarksBaseline:
    """Estimates facial landmarks using MediaPipe Face Mesh with 5-frame moving average."""

    def __init__(
        self,
        max_num_faces: int = 1,
        refine_landmarks: bool = True,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        smooth_window: int = 5,
    ) -> None:
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=max_num_faces,
            refine_landmarks=refine_landmarks,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self.smooth_window = smooth_window
        self._ear_history: deque = deque(maxlen=smooth_window)
        self._mar_history: deque = deque(maxlen=smooth_window)

    def extract_landmarks(
        self, frame_bgr: np.ndarray
    ) -> Optional[Dict[str, any]]:
        """Process a BGR frame and return computed EAR, MAR, landmarks, and face bbox.

        Returns None if no face is detected in the frame.
        """
        h, w, _ = frame_bgr.shape
        rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)

        if not results.multi_face_landmarks:
            # Clear smoothing queue on face loss to avoid carrying stale data
            self._ear_history.clear()
            self._mar_history.clear()
            return None

        face_landmarks = results.multi_face_landmarks[0]
        pts = np.array(
            [[lm.x * w, lm.y * h] for lm in face_landmarks.landmark],
            dtype=np.float32,
        )

        # Left & Right eye points
        left_eye_pts = pts[LEFT_EYE_INDICES]
        right_eye_pts = pts[RIGHT_EYE_INDICES]

        left_ear = calculate_ear(left_eye_pts)
        right_ear = calculate_ear(right_eye_pts)
        raw_avg_ear = (left_ear + right_ear) / 2.0

        # Mouth points (inner lip)
        corner_left = pts[MOUTH_CORNER_LEFT]
        corner_right = pts[MOUTH_CORNER_RIGHT]
        v_pairs = [(pts[top], pts[bottom]) for top, bottom in MOUTH_INNER_PAIRS]
        raw_mar = calculate_mar(corner_left, corner_right, v_pairs)

        # 5-frame moving average smoothing to eliminate jitter
        self._ear_history.append(raw_avg_ear)
        self._mar_history.append(raw_mar)
        smoothed_ear = float(np.mean(self._ear_history))
        smoothed_mar = float(np.mean(self._mar_history))

        # Bounding boxes
        x_min, y_min = np.min(pts, axis=0)
        x_max, y_max = np.max(pts, axis=0)
        face_bbox = (
            max(0, int(x_min)),
            max(0, int(y_min)),
            min(w, int(x_max)),
            min(h, int(y_max)),
        )

        return {
            "ear": round(smoothed_ear, 3),
            "raw_ear": round(float(raw_avg_ear), 3),
            "left_ear": round(float(left_ear), 3),
            "right_ear": round(float(right_ear), 3),
            "mar": round(smoothed_mar, 3),
            "raw_mar": round(float(raw_mar), 3),
            "face_bbox": face_bbox,
            "landmarks": pts,
        }

    def reset_smoothing(self) -> None:
        """Reset the moving average history."""
        self._ear_history.clear()
        self._mar_history.clear()

    def close(self) -> None:
        """Release FaceMesh resources."""
        if hasattr(self, "face_mesh") and self.face_mesh is not None:
            self.face_mesh.close()
