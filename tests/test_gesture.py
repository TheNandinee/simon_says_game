"""
Phase 3 — Gesture Detection Test
---------------------------------
Live webcam feed with hand landmark overlay and wave detection.

Controls:
  Click the preview window first, then:
    Q / ESC  — quit
    R        — reset wave detector state

  OR type in terminal:
    q + Enter  — quit
    r + Enter  — reset
"""

import sys
import os
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
from src.gesture.camera   import CameraStream
from src.gesture.detector import WaveDetector, draw_debug_hud


# ── Shared flags ───────────────────────────────────────────────────────
_quit_flag  = threading.Event()
_reset_flag = threading.Event()


def _terminal_listener():
    print("  [Terminal] q=quit   r=reset   (then Enter)")
    while not _quit_flag.is_set():
        try:
            cmd = input().strip().lower()
        except EOFError:
            break
        if cmd == "q":
            _quit_flag.set()
        elif cmd == "r":
            _reset_flag.set()
            print("  [Terminal] Detector reset.")


def main():
    print("\n  Phase 3 — Wave Gesture Detection")
    print("  ──────────────────────────────────")
    print("  Show your hand to the camera and WAVE side-to-side.")
    print("  A green border + WAVE! text confirms detection.\n")

    # ── Init ────────────────────────────────────────────────────────────
    cam      = CameraStream(device_index=0, width=640, height=480)
    detector = WaveDetector(
        buffer_size     = 30,
        reversal_thresh = 3,
        time_window     = 1.5,
        cooldown        = 1.5,
    )

    try:
        cam.start()
        print("  Camera ready.\n")
    except RuntimeError as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    threading.Thread(target=_terminal_listener, daemon=True).start()

    # ── Stats ────────────────────────────────────────────────────────────
    wave_count   = 0
    fps_counter  = 0
    fps_start    = time.time()
    current_fps  = 0.0
    last_wave_ts = 0.0

    win = "Simon Says | Phase 3 — Wave Detection | Q=quit"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    while not _quit_flag.is_set():

        frame = cam.get_frame()
        if frame is None:
            continue

        # ── Reset ────────────────────────────────────────────────────────
        if _reset_flag.is_set():
            _reset_flag.clear()
            detector.reset()
            wave_count = 0

        # ── Process ──────────────────────────────────────────────────────
        result = detector.process(frame)

        if result["wave"]:
            wave_count  += 1
            last_wave_ts = time.time()
            print(f"  👋  WAVE detected! (total: {wave_count})")

        # ── HUD ──────────────────────────────────────────────────────────
        since_wave = time.time() - last_wave_ts if last_wave_ts else 999
        instruction = (
            "👋 WAVE DETECTED!" if since_wave < 1.0
            else "Wave your hand side-to-side..."
        )

        display = draw_debug_hud(
            frame,
            result,
            score=wave_count,
            instruction=instruction,
        )

        # FPS overlay
        fps_counter += 1
        elapsed = time.time() - fps_start
        if elapsed >= 1.0:
            current_fps = fps_counter / elapsed
            fps_counter = 0
            fps_start   = time.time()

        cv2.putText(
            display, f"FPS: {current_fps:.1f}",
            (display.shape[1] - 110, display.shape[0] - 12),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (150, 150, 150), 1, cv2.LINE_AA,
        )

        cv2.imshow(win, display)

        # ── Key handling (window must be focused) ────────────────────────
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            _quit_flag.set()
        elif key == ord("r"):
            detector.reset()
            wave_count = 0
            print("  [Window] Detector reset.")

    # ── Cleanup ──────────────────────────────────────────────────────────
    detector.close()
    cam.stop()
    cv2.destroyAllWindows()
    print(f"\n  Session ended. Total waves detected: {wave_count}\n")


if __name__ == "__main__":
    main()