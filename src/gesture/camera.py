"""
Camera Stream Module
--------------------
Provides CameraStream: a thread-safe webcam capture class.
- Runs capture in a background daemon thread (no frame-drop lag)
- Exposes get_frame() → raw BGR numpy array
- Exposes get_jpeg() → JPEG-encoded bytes (for web streaming)
- Graceful start / stop lifecycle
"""

import cv2
import threading
import time
import numpy as np


class CameraStream:
    """
    Thread-safe webcam capture.
    Usage:
        cam = CameraStream()
        cam.start()
        frame = cam.get_frame()   # numpy BGR array
        jpeg  = cam.get_jpeg()    # bytes
        cam.stop()
    """

    def __init__(self, device_index: int = 0, width: int = 640, height: int = 480):
        self.device_index = device_index
        self.width = width
        self.height = height

        self._cap: cv2.VideoCapture | None = None
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

        # JPEG encode params — quality 80 is a good speed/quality balance
        self._encode_params = [cv2.IMWRITE_JPEG_QUALITY, 80]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> "CameraStream":
        """Open the device and begin background capture. Returns self for chaining."""
        self._cap = cv2.VideoCapture(self.device_index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Cannot open camera at index {self.device_index}. "
                "Check that no other app is using it and permissions are granted."
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, 30)

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

        # Wait until at least one frame is available
        deadline = time.time() + 5.0
        while self._frame is None and time.time() < deadline:
            time.sleep(0.05)
        if self._frame is None:
            raise RuntimeError("Camera opened but no frames received within 5 seconds.")

        return self

    def stop(self):
        """Stop the capture thread and release the device."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        if self._cap:
            self._cap.release()
        self._cap = None
        self._frame = None

    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Frame access
    # ------------------------------------------------------------------

    def get_frame(self) -> np.ndarray | None:
        """Return the latest BGR frame as a numpy array, or None if unavailable."""
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def get_jpeg(self) -> bytes | None:
        """Return the latest frame encoded as JPEG bytes, or None if unavailable."""
        frame = self.get_frame()
        if frame is None:
            return None
        success, buffer = cv2.imencode(".jpg", frame, self._encode_params)
        if not success:
            return None
        return bytes(buffer)

    def get_frame_with_overlay(self, text_lines: list[str]) -> np.ndarray | None:
        """
        Return a copy of the latest frame with HUD text overlaid.
        text_lines: list of strings drawn top-left, stacked vertically.
        """
        frame = self.get_frame()
        if frame is None:
            return None
        overlay = frame.copy()
        x, y_start, dy = 10, 30, 28
        font = cv2.FONT_HERSHEY_SIMPLEX
        for i, line in enumerate(text_lines):
            y = y_start + i * dy
            # Shadow
            cv2.putText(overlay, line, (x + 1, y + 1), font, 0.7, (0, 0, 0), 2, cv2.LINE_AA)
            # Text
            cv2.putText(overlay, line, (x, y), font, 0.7, (0, 255, 120), 2, cv2.LINE_AA)
        return overlay

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _capture_loop(self):
        """Background thread: continuously read frames from the device."""
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                break
            ret, frame = self._cap.read()
            if not ret:
                # Transient failure — skip frame
                time.sleep(0.01)
                continue
            # Flip horizontally so it acts like a mirror (more natural for users)
            frame = cv2.flip(frame, 1)
            with self._lock:
                self._frame = frame