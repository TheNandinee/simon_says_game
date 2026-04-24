"""
Phase 4 — Audio Detection Test
--------------------------------
Visualises microphone input in the terminal.
Shows live RMS bar, band energy bar, and fires
CLAP / SHH events as they are detected.

Controls (type in terminal + Enter):
  q  — quit
  c  — manually trigger a fake clap (sanity check)
  s  — manually trigger a fake shh  (sanity check)
  t  — print current threshold values
"""

import sys
import os
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.audio.detector import AudioDetector


# ── Shared flags ───────────────────────────────────────────────────────
_quit_flag         = threading.Event()
_fake_clap_flag    = threading.Event()
_fake_shh_flag     = threading.Event()
_print_thresh_flag = threading.Event()


def _terminal_listener():
    print("  [Terminal] q=quit  c=fake-clap  s=fake-shh  t=thresholds")
    while not _quit_flag.is_set():
        try:
            cmd = input().strip().lower()
        except EOFError:
            break
        if   cmd == "q": _quit_flag.set()
        elif cmd == "c": _fake_clap_flag.set()
        elif cmd == "s": _fake_shh_flag.set()
        elif cmd == "t": _print_thresh_flag.set()


def _bar(value: float, maximum: float, width: int = 30, char: str = "█") -> str:
    filled = int(min(value / maximum, 1.0) * width)
    return char * filled + "░" * (width - filled)


def main():
    print("\n  Phase 4 — Audio Detection Test")
    print("  ────────────────────────────────")
    print("  Make noise at your mic:")
    print("    👏 CLAP  — sharp, loud, short")
    print("    🤫 SHH   — sustained shushing sound\n")

    detector = AudioDetector(
        sample_rate      = 44100,
        chunk_size       = 1024,
        spike_thresh     = 0.03,
        spike_ratio      = 6.0,
        shh_band         = (1000, 8000),
        shh_thresh       = 0.008,
        shh_min_duration = 0.3,
        clap_cooldown    = 0.4,
        shh_cooldown     = 0.8,
    )

    try:
        detector.start()
        print("  ✅  Microphone open — listening...\n")
    except Exception as e:
        print(f"  ❌  Could not open microphone: {e}")
        print("      Check mic permissions: System Preferences → Privacy → Microphone")
        sys.exit(1)

    threading.Thread(target=_terminal_listener, daemon=True).start()

    clap_count = 0
    shh_count  = 0
    last_event = ""
    last_event_ts = 0.0

    RESET  = "\033[0m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    RED    = "\033[91m"
    BOLD   = "\033[1m"
    CLEAR  = "\033[2K\r"

    print(f"  {'RMS LEVEL':<14} {'SHH BAND':<14} {'EVENT'}")
    print(f"  {'─'*13} {'─'*13} {'─'*20}")

    try:
        while not _quit_flag.is_set():

            # Handle fake trigger flags (sanity checks)
            if _fake_clap_flag.is_set():
                _fake_clap_flag.clear()
                clap_count += 1
                last_event    = f"{GREEN}{BOLD}👏 FAKE CLAP{RESET}"
                last_event_ts = time.time()
                print(f"\n  {GREEN}{BOLD}[FAKE] 👏 CLAP fired (total: {clap_count}){RESET}")

            if _fake_shh_flag.is_set():
                _fake_shh_flag.clear()
                shh_count  += 1
                last_event    = f"{CYAN}{BOLD}🤫 FAKE SHH{RESET}"
                last_event_ts = time.time()
                print(f"\n  {CYAN}{BOLD}[FAKE] 🤫 SHH  fired (total: {shh_count}){RESET}")

            if _print_thresh_flag.is_set():
                _print_thresh_flag.clear()
                print(f"\n  spike_thresh={detector.spike_thresh}  "
                      f"spike_ratio={detector.spike_ratio}  "
                      f"shh_thresh={detector.shh_thresh}  "
                      f"shh_min_duration={detector.shh_min_duration}s")

            # ── Poll detector ───────────────────────────────────────
            result = detector.update()

            if result["clap"]:
                clap_count   += 1
                last_event    = f"{GREEN}{BOLD}👏 CLAP!{RESET}"
                last_event_ts = time.time()
                # Print on new line so it's clearly visible
                print(f"\n  {GREEN}{BOLD}👏  CLAP detected! (total: {clap_count}){RESET}")

            if result["shh"]:
                shh_count    += 1
                last_event    = f"{CYAN}{BOLD}🤫 SHH!{RESET}"
                last_event_ts = time.time()
                print(f"\n  {CYAN}{BOLD}🤫  SHH  detected! (total: {shh_count}){RESET}")

            # ── Live bars ────────────────────────────────────────────
            rms_val      = result["rms"]
            band_val     = result["band_rms"]
            shh_building = result["shh_active"]

            rms_color  = RED if rms_val > detector.spike_thresh else RESET
            band_color = CYAN if shh_building else RESET

            rms_bar  = _bar(rms_val,  0.15, width=20)
            band_bar = _bar(band_val, 0.05, width=20)

            event_label = ""
            if time.time() - last_event_ts < 1.2:
                event_label = last_event
            elif shh_building:
                event_label = f"{YELLOW}building shh...{RESET}"

            line = (
                f"  {rms_color}[{rms_bar}]{RESET} "
                f"{band_color}[{band_bar}]{RESET} "
                f"{event_label}"
            )
            print(f"{CLEAR}{line}", end="", flush=True)

            time.sleep(0.04)   # ~25 fps refresh

    except KeyboardInterrupt:
        pass

    detector.stop()
    print(f"\n\n  Session ended.")
    print(f"  Total CLAPs : {clap_count}")
    print(f"  Total SHHs  : {shh_count}\n")


if __name__ == "__main__":
    main()