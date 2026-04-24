"""
Gesture Detector Module (MediaPipe 0.10+ compatible)
-----------------------------------------------------
Uses MediaPipe Tasks HandLandmarker API (replaces mp.solutions in 0.10+).

Wave Detection Logic:
  - Track wrist X position across a rolling buffer
  - Count direction reversals (left<->right)
  - reversals >= threshold within time_window => WAVE
"""

import time
import collections
import threading
import urllib.request
import os
import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.components import containers as mp_containers

# ── Model download ─────────────────────────────────────────────────────
_MODEL_URL  = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")

def _ensure_model():
    if not os.path.exists(_MODEL_PATH):
        print("  [Gesture] Downloading MediaPipe hand model (~9 MB)...")
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        print("  [Gesture] Model downloaded.")

# ── Drawing helpers using new API ──────────────────────────────────────
_HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),
    (0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),
    (5,9),(9,13),(13,17),
]

def _draw_landmarks(frame, landmarks_list):
    """Draw hand skeleton directly from NormalizedLandmark list."""
    if not landmarks_list:
        return frame
    h, w = frame.shape[:2]
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks_list]
    for a, b in _HAND_CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], (0, 200, 255), 2, cv2.LINE_AA)
    for x, y in pts:
        cv2.circle(frame, (x, y), 4, (0, 255, 120), -1, cv2.LINE_AA)
        cv2.circle(frame, (x, y), 4, (0, 0, 0),     1,  cv2.LINE_AA)
    return frame


class WaveDetector:
    """
    Detects WAVE gesture using MediaPipe Tasks HandLandmarker (0.10+ API).
    """

    def __init__(
        self,
        buffer_size: int     = 30,
        reversal_thresh: int = 3,
        time_window: float   = 1.5,
        cooldown: float      = 1.5,
        min_hand_conf: float = 0.6,
        min_track_conf: float = 0.5,
    ):
        self.buffer_size     = buffer_size
        self.reversal_thresh = reversal_thresh
        self.time_window     = time_window
        self.cooldown        = cooldown

        _ensure_model()

        base_opts = mp_python.BaseOptions(model_asset_path=_MODEL_PATH)
        opts = mp_vision.HandLandmarkerOptions(
            base_options        = base_opts,
            running_mode        = mp_vision.RunningMode.IMAGE,
            num_hands           = 1,
            min_hand_detection_confidence  = min_hand_conf,
            min_hand_presence_confidence   = min_hand_conf,
            min_tracking_confidence        = min_track_conf,
        )
        self._landmarker = mp_vision.HandLandmarker.create_from_options(opts)

        self._positions: collections.deque = collections.deque(maxlen=buffer_size)
        self._last_wave_time: float = 0.0
        self._wave_detected: bool   = False

    # ------------------------------------------------------------------
    def process(self, bgr_frame: np.ndarray) -> dict:
        self._wave_detected = False

        rgb        = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image   = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        detection  = self._landmarker.detect(mp_image)

        annotated     = bgr_frame.copy()
        hand_visible  = False
        wrist_x       = None
        landmarks_out = None

        if detection.hand_landmarks:
            hand_visible  = True
            landmarks_out = detection.hand_landmarks[0]   # list of NormalizedLandmark

            _draw_landmarks(annotated, landmarks_out)

            wrist_x = landmarks_out[0].x   # landmark 0 = WRIST
            now     = time.time()
            self._positions.append((now, wrist_x))
            self._wave_detected = self._check_wave(now)

        else:
            self._positions.clear()

        if self._wave_detected:
            h, w = annotated.shape[:2]
            cv2.rectangle(annotated, (0, 0), (w, h), (0, 255, 120), 6)
            cv2.putText(
                annotated, "WAVE!", (w // 2 - 70, h // 2),
                cv2.FONT_HERSHEY_DUPLEX, 2.2, (0, 255, 120), 3, cv2.LINE_AA,
            )

        return {
            "wave"        : self._wave_detected,
            "hand_visible": hand_visible,
            "wrist_x"     : wrist_x,
            "annotated"   : annotated,
            "landmarks"   : landmarks_out,
        }

    def reset(self):
        self._positions.clear()
        self._last_wave_time = 0.0
        self._wave_detected  = False

    def close(self):
        self._landmarker.close()

    # ------------------------------------------------------------------
    def _check_wave(self, now: float) -> bool:
        if now - self._last_wave_time < self.cooldown:
            return False
        cutoff = now - self.time_window
        recent = [(t, x) for t, x in self._positions if t >= cutoff]
        if len(recent) < 6:
            return False
        xs        = [x for _, x in recent]
        reversals = 0
        prev_dir  = None
        for i in range(1, len(xs)):
            dx = xs[i] - xs[i - 1]
            if abs(dx) < 0.01:
                continue
            cur_dir = 1 if dx > 0 else -1
            if prev_dir is not None and cur_dir != prev_dir:
                reversals += 1
            prev_dir = cur_dir
        if reversals >= self.reversal_thresh:
            self._last_wave_time = now
            self._positions.clear()
            return True
        return False


# ── HUD helper ─────────────────────────────────────────────────────────
def draw_debug_hud(
    frame: np.ndarray,
    result: dict,
    score: int   = 0,
    instruction: str = "",
) -> np.ndarray:
    out  = result["annotated"].copy()
    h, w = out.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX

    def _text(txt, x, y, color=(200,200,200), scale=0.6, thick=2):
        cv2.putText(out, txt, (x+1,y+1), font, scale, (0,0,0),  thick+1, cv2.LINE_AA)
        cv2.putText(out, txt, (x, y),    font, scale, color,     thick,   cv2.LINE_AA)

    bar = out.copy()
    cv2.rectangle(bar, (0,0), (w,50), (20,20,20), -1)
    cv2.addWeighted(bar, 0.55, out, 0.45, 0, out)

    hand_color = (0,255,120) if result["hand_visible"] else (60,60,200)
    hand_label = "Hand: VISIBLE" if result["hand_visible"] else "Hand: NOT DETECTED"
    _text(hand_label, 10, 30, hand_color, scale=0.65, thick=2)

    if result["wrist_x"] is not None:
        bx = 20
        by = 42
        bw = int(result["wrist_x"] * (w - 40))
        cv2.rectangle(out, (bx, by), (bx + w - 40, by + 8), (50,50,50),   -1)
        cv2.rectangle(out, (bx, by), (bx + bw,     by + 8), (0,200,255),  -1)

    if instruction:
        _text(f"{instruction}", 10, h - 50, (255,220,50), scale=0.7, thick=2)
    if score:
        _text(f"Score: {score}", w - 130, 30, (255,255,255), scale=0.65)

    return out
