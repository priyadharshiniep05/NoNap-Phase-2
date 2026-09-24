"""Capture package for webcam ingest."""

from server.app.capture.webcam_worker import webcam_worker, WebcamWorker

__all__ = ["webcam_worker", "WebcamWorker"]
