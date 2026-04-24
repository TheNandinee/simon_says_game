"""
Speech test — shows EXACTLY what Vosk hears so you can tune it.
Say meow in different ways: "meow", "miaow", "me-ow", "myow"
"""

import sys, os, time, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.audio.speech import SpeechDetector, _is_meow

_quit = threading.Event()

def _listen():
    while not _quit.is_set():
        try:
            cmd = input().strip().lower()
            if cmd == "q":
                _quit.set()
        except EOFError:
            break

def main():
    print("\n  Meow Detection Test — fuzzy matching")
    print("  ──────────────────────────────────────")
    print("  Vosk hears you and shows the raw transcript.")
    print("  Try saying: meow / miaow / me-ow / myow / mew")
    print("  Type q + Enter to quit\n")

    det = SpeechDetector(cooldown=1.0)
    try:
        det.start()
        print("  ✅  Listening...\n")
    except Exception as e:
        print(f"  ❌  {e}"); sys.exit(1)

    threading.Thread(target=_listen, daemon=True).start()

    RS="\033[0m"; GR="\033[92m"; YE="\033[93m"; DIM="\033[2m"; BOLD="\033[1m"
    meow_count = 0

    while not _quit.is_set():
        result = det.update()

        # Always print what was heard (so you can see mismatches)
        if det.last_heard and (time.time() - det.last_heard_at) < 0.15:
            matched = _is_meow(det.last_heard)
            tag     = f"{GR}✅ MEOW MATCH{RS}" if matched else f"{DIM}no match{RS}"
            print(f"  heard: {YE}\"{det.last_heard}\"{RS}  →  {tag}")

        if result["meow"]:
            meow_count += 1
            print(f"  {GR}{BOLD}🐱  MEOW fired! (total: {meow_count}){RS}\n")

        time.sleep(0.03)

    det.stop()
    print(f"\n  Total MEOWs: {meow_count}\n")

if __name__ == "__main__":
    main()
