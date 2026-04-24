"""
Phase 2 — Camera Test (macOS-compatible)
-----------------------------------------
Opens the webcam, shows the live feed in an OpenCV window.

macOS fix: cv2.waitKey() only works when the PREVIEW WINDOW
is focused. Click the camera window once, THEN press keys.

Controls (with camera window focused):
  Q or ESC  — quit
  S         — save a snapshot
  O         — toggle overlay HUD

Terminal fallback (works from terminal anytime):
  Type  q + Enter  to quit, s + Enter to snap, o + Enter to toggle
"""

import sys
import os
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
from src.gesture.camera import CameraStream

_quit_flag     = threading.Event()
_snapshot_flag = threading.Event()
_overlay_flag  = threading.Event()
_overlay_flag.set()   # overlay ON by default


def _terminal_listener():
    print("  [Terminal] Type  q=quit  s=snapshot  o=overlay  then Enter")
    while not _quit_flag.is_set():
        try:
            cmd = input().strip().lower()
        except EOFError:
            break
        if cmd == "q":
            print("  [Terminal] Quit requested.")
            _quit_flag.set()
        elif cmd == "s":
            _snapshot_flag.set()
        elif cmd == "o":
            if _overlay_flag.is_set():
                _overlay_flag.clear()
                print("  [Terminal] Overlay OFF")
            else:
                _overlay_flag.set()
                print("  [Terminal] Overlay ON")


def main():
    print("\n  Phase 2 — Camera Test (macOS-compatible)")
    print("  ─────────────────────────────────────────")
    print("  Option A: Click the preview window → press Q / S / O")
    print("  Option B: Type  q / s / o  in THIS terminal → Enter")
    print("  ─────────────────────────────────────────\n")

    cam = CameraStream(device_index=0, width=640, height=480)
    try:
        print("  Starting camera...")
        cam.start()
        print("  Camera running — preview window opening now\n")
    except RuntimeError as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    threading.Thread(target=_terminal_listener, daemon=True).start()

    fps_counter, fps_start, current_fps = 0, time.time(), 0.0
    win = "Simon Says | Click window then Q=quit S=snap O=overlay"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    while not _quit_flag.is_set():
        if _overlay_flag.is_set():
            frame = cam.get_frame_with_overlay([
                "Simon Says — Camera Test",
                f"FPS: {current_fps:.1f}  |  640x480",
                "CLICK THIS WINDOW: Q=quit  S=snapshot  O=overlay",
                "OR type those keys in the terminal",
            ])
        else:
            frame = cam.get_frame()

        if frame is None:
            continue

        cv2.imshow(win, frame)

        fps_counter += 1
        elapsed = time.time() - fps_start
        if elapsed >= 1.0:
            current_fps = fps_counter / elapsed
            fps_counter = 0
            fps_start = time.time()

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            print("  [Window] Quit.")
            _quit_flag.set()
        elif key == ord("s"):
            _snapshot_flag.set()
        elif key == ord("o"):
            if _overlay_flag.is_set():
                _overlay_flag.clear(); print("  [Window] Overlay OFF")
            else:
                _overlay_flag.set();  print("  [Window] Overlay ON")

        if _snapshot_flag.is_set():
            _snapshot_flag.clear()
            raw = cam.get_frame()
            if raw is not None:
                fname = f"snapshot_{int(time.time())}.jpg"
                cv2.imwrite(fname, raw)
                print(f"  Snapshot saved -> {fname}")

    cam.stop()
    cv2.destroyAllWindows()
    print("  Camera released cleanly.\n")


if __name__ == "__main__":
    main()
