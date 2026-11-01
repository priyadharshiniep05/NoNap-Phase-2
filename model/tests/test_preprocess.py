"""Unit tests for CLAHE and low-light preprocessing."""

import numpy as np
import pytest
from nonap_model.preprocess import preprocess_frame


def test_preprocess_standard_frame():
    """Verify standard frame processing returns expected dimensions and type."""
    # Synthetic normal brightness image (mean ~128)
    frame = np.full((480, 640, 3), 128, dtype=np.uint8)
    enhanced, is_night, mean_lum = preprocess_frame(frame)

    assert enhanced.shape == frame.shape
    assert enhanced.dtype == np.uint8
    assert not is_night
    assert 100 < mean_lum < 150


def test_preprocess_low_light_night_mode():
    """Verify night mode triggers on low-light frames."""
    # Dark synthetic image (mean ~30)
    dark_frame = np.full((240, 320, 3), 30, dtype=np.uint8)
    enhanced, is_night, mean_lum = preprocess_frame(dark_frame, night_threshold=75.0)

    assert is_night
    assert mean_lum < 75.0
    assert enhanced.shape == dark_frame.shape


def test_preprocess_invalid_frame():
    """Verify error on empty or None input."""
    with pytest.raises(ValueError):
        preprocess_frame(None)

    with pytest.raises(ValueError):
        preprocess_frame(np.array([]))
