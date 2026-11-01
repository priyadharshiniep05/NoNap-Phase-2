"""Standalone webcam demonstration script with real-time HUD telemetry overlay.

Run via: python -m nonap_model.demo
Press 'q' or ESC to exit.
"""

import os
import sys
import time
import cv2
import numpy as np

from nonap_model.engine import predict, get_engine


def draw_hud(frame: np.ndarray, result: dict, fps: float) -> np.ndarray:
    """Draw professional dark-themed telemetry overlay on frame."""
    h, w, _ = frame.shape
    canvas = frame.copy()

    status = result["status"]
    conf = result["confidence"]
    metrics = result["metrics"]
    face_bbox = result.get("face_bbox")

    # Define color scheme based on status
    if status == "drowsy":
        status_color = (68, 68, 239)  # Red (#EF4444 in BGR)
    elif status == "yawning":
        status_color = (11, 158, 245)  # Amber (#F59E0B in BGR)
    elif status == "alert":
        status_color = (94, 197, 34)   # Green (#22C55E in BGR)
    else:
        status_color = (148, 163, 184) # Muted slate

    # Draw face bounding box if present
    if face_bbox is not None:
        x1, y1, x2, y2 = face_bbox
        cv2.rectangle(canvas, (x1, y1), (x2, y2), status_color, 2)
        # Corner brackets
        length = 20
        thick = 3
        # Top-left
        cv2.line(canvas, (x1, y1), (x1 + length, y1), status_color, thick)
        cv2.line(canvas, (x1, y1), (x1, y1 + length), status_color, thick)
        # Top-right
        cv2.line(canvas, (x2, y1), (x2 - length, y1), status_color, thick)
        cv2.line(canvas, (x2, y1), (x2, y1 + length), status_color, thick)
        # Bottom-left
        cv2.line(canvas, (x1, y2), (x1 + length, y2), status_color, thick)
        cv2.line(canvas, (x1, y2), (x1, y2 - length), status_color, thick)
        # Bottom-right
        cv2.line(canvas, (x2, y2), (x2 - length, y2), status_color, thick)
        cv2.line(canvas, (x2, y2), (x2, y2 - length), status_color, thick)

    # Semi-transparent HUD overlay panel on the top-left
    panel_w = 320
    panel_h = 220
    sub_img = canvas[15 : 15 + panel_h, 15 : 15 + panel_w]
    dark_rect = np.full(sub_img.shape, (26, 23, 15), dtype=np.uint8)  # Navy #0F172A
    res = cv2.addWeighted(sub_img, 0.25, dark_rect, 0.75, 1.0)
    canvas[15 : 15 + panel_h, 15 : 15 + panel_w] = res

    # Border for HUD
    cv2.rectangle(canvas, (15, 15), (15 + panel_w, 15 + panel_h), (50, 40, 30), 1)

    # Header / Title
    cv2.putText(
        canvas, "NONAP REAL-TIME HUD", (30, 42),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (238, 211, 34), 2 # Cyan accent
    )

    # Status badge
    status_text = f"STATUS: {status.upper()}"
    cv2.putText(
        canvas, status_text, (30, 72),
        cv2.FONT_HERSHEY_SIMPLEX, 0.65, status_color, 2
    )

    # Metrics
    ear_val = metrics.get("ear", 0.0)
    mar_val = metrics.get("mar", 0.0)
    perclos_val = metrics.get("perclos", 0.0)
    closed_s = metrics.get("eyes_closed_s", 0.0)
    yawns_cnt = metrics.get("yawns_5min", 0)
    latency_ms = metrics.get("latency_ms", 0.0)
    backend_name = metrics.get("backend", "baseline")

    y_pos = 100
    line_h = 22
    metrics_lines = [
        f"EAR: {ear_val:.3f} | MAR: {mar_val:.3f}",
        f"PERCLOS: {perclos_val * 100:.1f}% | Closed: {closed_s:.1f}s",
        f"Yawns (5m): {yawns_cnt} | Conf: {conf * 100:.0f}%",
        f"Engine: {backend_name.title()} ({latency_ms:.1f}ms)",
        f"FPS: {fps:.1f} | Press 'q' to quit",
    ]

    for line in metrics_lines:
        cv2.putText(
            canvas, line, (30, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX, 0.44, (240, 245, 250), 1
        )
        y_pos += line_h

    return canvas


def run_demo(webcam_index: int = 0) -> None:
    """Run real-time webcam demo."""
    cap = cv2.VideoCapture(webcam_index)
    if not cap.isOpened():
        print(f"ERROR: Cannot access webcam at index {webcam_index}.")
        print("Please ensure camera permissions are granted in macOS System Settings.")
        sys.exit(1)

    print("==================================================")
    print("  NoNap Real-Time Drowsiness Detection Demo")
    print(f"  Webcam Index: {webcam_index}")
    print("  Press 'q' or ESC in the video window to quit.")
    print("==================================================")

    engine = get_engine()
    prev_time = time.time()
    fps = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("Warning: Empty frame received from webcam.")
                time.sleep(0.05)
                continue

            curr_time = time.time()
            dt = curr_time - prev_time
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps > 0 else 1.0 / dt
            prev_time = curr_time

            result = engine.predict(frame)
            annotated = draw_hud(frame, result, fps)

            # Print concise terminal status
            status = result["status"]
            ear = result["metrics"]["ear"]
            mar = result["metrics"]["mar"]
            lat = result["metrics"]["latency_ms"]
            print(
                f"\r[{status.upper():<7}] EAR: {ear:.3f} | MAR: {mar:.3f} | "
                f"Latency: {lat:4.1f}ms | FPS: {fps:4.1f}  ",
                end="",
                flush=True,
            )

            cv2.imshow("NoNap - Real-Time Driver Drowsiness HUD", annotated)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):  # 'q' or ESC
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        engine.close()
        print("\nWebcam session ended gracefully.")


if __name__ == "__main__":
    idx = int(os.environ.get("WEBCAM_INDEX", 0))
    run_demo(webcam_index=idx)
