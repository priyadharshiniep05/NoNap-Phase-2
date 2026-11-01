"""Image preprocessing module for NoNap.

Applies CLAHE (Contrast Limited Adaptive Histogram Equalization) on the LAB
color space L-channel, with automatic low-light / night mode enhancement.
"""

from typing import Tuple
import cv2
import numpy as np


def preprocess_frame(
    frame: np.ndarray,
    clip_limit: float = 2.0,
    tile_grid_size: Tuple[int, int] = (8, 8),
    night_threshold: float = 75.0,
    gamma: float = 1.3,
) -> Tuple[np.ndarray, bool, float]:
    """Preprocess an input BGR frame with CLAHE and optional night enhancement.

    Args:
        frame: BGR image frame as numpy array.
        clip_limit: Threshold for contrast limiting in CLAHE.
        tile_grid_size: Grid size for histogram equalization.
        night_threshold: Mean luminance threshold below which night mode engages.
        gamma: Gamma correction factor for low-light enhancement.

    Returns:
        Tuple containing:
            - enhanced_bgr: Processed BGR frame.
            - is_night_mode: Boolean indicating if night enhancement was triggered.
            - mean_luminance: Average brightness value in the L-channel [0, 255].
    """
    if frame is None or frame.size == 0:
        raise ValueError("Invalid or empty input frame provided to preprocess_frame.")

    # Convert to LAB color space to separate lightness from color
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    # Compute mean luminance
    mean_luminance = float(np.mean(l_channel))
    is_night_mode = mean_luminance < night_threshold

    # Apply adaptive gamma correction if ambient light is low
    if is_night_mode and gamma > 0:
        inv_gamma = 1.0 / gamma
        lut = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        l_channel = cv2.LUT(l_channel, lut)

    # Apply CLAHE to L-channel
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    l_enhanced = clahe.apply(l_channel)

    # Merge channels back and convert to BGR
    enhanced_lab = cv2.merge((l_enhanced, a_channel, b_channel))
    enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    return enhanced_bgr, is_night_mode, mean_luminance
