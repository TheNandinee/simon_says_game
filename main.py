"""
Simon Says Game — Main Entry Point
Phase 1: Environment validation only.
Later phases will replace this with full integration.
"""

import sys

def check_dependencies():
    deps = {
        "cv2": "OpenCV",
        "mediapipe": "MediaPipe",
        "sounddevice": "SoundDevice",
        "numpy": "NumPy",
        "scipy": "SciPy",
        "fastapi": "FastAPI",
        "uvicorn": "Uvicorn",
    }
    all_ok = True
    for module, name in deps.items():
        try:
            __import__(module)
            print(f"  ✅  {name}")
        except ImportError:
            print(f"  ❌  {name} — NOT FOUND")
            all_ok = False
    return all_ok

if __name__ == "__main__":
    print("\n🎮  Simon Says — Dependency Check\n")
    ok = check_dependencies()
    if ok:
        print("\n✅  All dependencies satisfied. Ready for Phase 2.\n")
        sys.exit(0)
    else:
        print("\n❌  Missing dependencies. Re-run pip install commands.\n")
        sys.exit(1)