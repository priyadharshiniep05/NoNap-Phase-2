"""MediaPipe FaceMesh baseline landmark extraction for EAR and MAR.

Extracts eye aspect ratio (EAR) and mouth aspect ratio (MAR) from 468 face landmarks,
along with face bounding box and eye/mouth regions of interest.
"""

from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
import mediapipe as mp


# Landmark indices for Left and Right eyes in MediaPipe Face Mesh
# Left eye: [outer, top1, top2, inner, bottom2, bottom1]
LEFT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
# Right eye: [inner, top1, top2, outer, bottom2, bottom1]
RIGHT_EYE_INDICES = [33, 160, 158, 133, 153, 144]

# Mouth indices: horizontal corners + 3 vertical coordinate pairs
MOUTH_HORIZONTAL = (78, 308)
MOUTH_VERTICAL_PAIRS = [(13, 14), (81, 178), (311, 402)]


def _euclidean_distance(p1: np.ndarray, p2: np.ndarray) -> float:
    """Compute Euclidean distance between two 2D points."""
    return float(np.linalg.norm(p1 - p2))


def calculate_ear(eye_points: np.ndarray) -> float:
    """Calculate the Eye Aspect Ratio (EAR) for 6 ordered landmark points.

    Points order: [p0, p1, p2, p3, p4, p5] where:
      p0, p3 are the horizontal corners
      (p1, p5) and (p2, p4) are the vertical pairs
    """
    if len(eye_points) < 6:
        return 0.0

    # Vertical distances
    v1 = _euclidean_distance(eye_points[1], eye_points[5])
    v2 = _euclidean_distance(eye_points[2], eye_points[4])
    # Horizontal distance
    h = _euclidean_distance(eye_points[0], eye_points[3])

    if h <= 1e-6:
        return 0.0
    return (v1 + v2) / (2.0 * h)


def calculate_mar(
    corner_left: np.ndarray,
    corner_right: np.ndarray,
    vertical_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> float:
    """Calculate Mouth Aspect Ratio (MAR)."""
    h = _euclidean_distance(corner_left, corner_right)
    if h <= 1e-6:
        return 0.0

    v_sum = sum(_euclidean_distance(top, bottom) for top, bottom in vertical_pairs)
    return v_sum / (2.0 * h)


class LandmarksBaseline:
    """Estimates facial landmarks using MediaPipe Face Mesh."""

    def __init__(
        self,
        max_num_faces: int = 1,
        refine_landmarks: bool = True,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=max_num_faces,
            refine_landmarks=refine_landmarks,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

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
        avg_ear = (left_ear + right_ear) / 2.0

        # Mouth points
        corner_left = pts[MOUTH_HORIZONTAL[0]]
        corner_right = pts[MOUTH_HORIZONTAL[1]]
        v_pairs = [(pts[top], pts[bottom]) for top, bottom in MOUTH_VERTICAL_PAIRS]
        mar = calculate_mar(corner_left, corner_right, v_pairs)

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
            "ear": float(avg_ear),
            "left_ear": float(left_ear),
            "right_ear": float(right_ear),
            "mar": float(mar),
            "face_bbox": face_bbox,
            "landmarks": pts,
        }

    def close(self) -> None:
        """Release FaceMesh resources."""
        if hasattr(self, "face_mesh") and self.face_mesh is not None:
            self.face_mesh.close()
