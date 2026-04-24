"""
Phase 5 — Game Logic Terminal Test
------------------------------------
Fully playable Simon Says in the terminal.
No camera or microphone needed — keyboard simulates gestures.

Controls (type + Enter):
  w  → submit WAVE
  c  → submit CLAP
  s  → submit SHH
  n  → submit nothing (simulate timeout)
  r  → restart game
  h  → show full round history
  q  → quit
"""

import sys
import os
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.game.logic     import SimonSaysGame
from src.game.constants import (
    STATE_IDLE, STATE_COUNTDOWN, STATE_PLAYING,
    STATE_WAITING, STATE_FEEDBACK, STATE_GAME_OVER,
    ACTION_WAVE, ACTION_CLAP, ACTION_SHH,
)


# ── Shared ─────────────────────────────────────────────────────────────
_quit_flag   = threading.Event()
_input_queue = []          # latest terminal command
_input_lock  = threading.Lock()


def _terminal_listener():
    cmds = {"w": ACTION_WAVE, "c": ACTION_CLAP, "s": ACTION_SHH}
    print("  [Input] w=wave  c=clap  s=shh  n=nothing  r=restart  h=history  q=quit")
    while not _quit_flag.is_set():
        try:
            raw = input().strip().lower()
        except EOFError:
            break
        with _input_lock:
            _input_queue.append(raw)


# ── Display helpers ────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
MAGENTA= "\033[95m"
DIM    = "\033[2m"
CLEAR  = "\033[2K\r"


def _heart(n: int, max_n: int) -> str:
    return "❤️  " * n + "🖤  " * (max_n - n)


def _progress_bar(value: float, total: float, width: int = 20) -> str:
    filled = int((value / max(total, 0.001)) * width)
    bar    = "█" * filled + "░" * (width - filled)
    color  = GREEN if value > total * 0.5 else YELLOW if value > total * 0.2 else RED
    return f"{color}[{bar}]{RESET}"


def _render(snap: dict, last_cmd: str):
    os.system("clear")
    state = snap["state"]

    print(f"\n  {BOLD}{'─'*50}{RESET}")
    print(f"  {BOLD}{CYAN}🎮  SIMON SAYS{RESET}   "
          f"Round {snap['round']}   "
          f"{DIM}{snap['difficulty']}{RESET}")
    print(f"  {'─'*50}")

    # Lives + score + streak
    print(f"\n  {_heart(snap['lives'], snap['max_lives'])}")
    print(f"  Score: {BOLD}{snap['score']}{RESET}   "
          f"Streak: {BOLD}{snap['streak']}🔥{RESET}" if snap['streak'] > 0
          else f"  Score: {BOLD}{snap['score']}{RESET}")

    print(f"\n  {'─'*50}")

    # State-specific display
    if state == STATE_IDLE:
        print(f"\n  {DIM}Press  r  to start the game...{RESET}\n")

    elif state == STATE_COUNTDOWN:
        n = int(snap["countdown_left"]) + 1
        print(f"\n  {BOLD}{YELLOW}  Get ready...  {n}{RESET}\n")

    elif state in (STATE_PLAYING, STATE_WAITING):
        instr = snap["instruction"]
        if snap["simon_says"]:
            print(f"\n  {BOLD}{GREEN}  ▶  {instr}{RESET}\n")
        else:
            print(f"\n  {BOLD}{RED}  ⚠   {instr}{RESET}\n")

        if state == STATE_WAITING:
            tl = snap["time_left"]
            tt = snap["time_limit"]
            print(f"  Time: {_progress_bar(tl, tt)}  {tl:.1f}s\n")
            print(f"  {DIM}w=wave  c=clap  s=shh  n=nothing{RESET}")
        else:
            print(f"  {DIM}(get ready...){RESET}")

    elif state == STATE_FEEDBACK:
        res = snap["last_result"]
        color = GREEN if res["is_positive"] else RED
        print(f"\n  {BOLD}{color}  {res['message']}{RESET}")
        if res["points"]:
            print(f"  {GREEN}  +{res['points']} points{RESET}\n")

    elif state == STATE_GAME_OVER:
        print(f"\n  {BOLD}{RED}  💀  GAME OVER{RESET}\n")
        print(f"  Final Score : {BOLD}{snap['score']}{RESET}")
        print(f"  Rounds      : {snap['round']}")
        print(f"\n  {DIM}Press  r  to play again,  q  to quit{RESET}\n")

    # Mini history
    history = snap["history"]
    if history:
        print(f"\n  {'─'*50}")
        print(f"  {DIM}Last rounds:{RESET}")
        for entry in reversed(history):
            icon = "✅" if entry["result_kind"] in ("correct","trap_pass") else "❌"
            pts  = f"+{entry['points']}" if entry["points"] else " 0"
            print(f"  {DIM}{icon} R{entry['round']:02d}  {entry['instruction']:<28}"
                  f"  {pts:>4}pt  {entry['message']}{RESET}")

    print(f"\n  {'─'*50}")
    print(f"  {DIM}Last key: [{last_cmd}]{RESET}")


def main():
    print("\n  Phase 5 — Simon Says Game Logic Test")
    print("  ──────────────────────────────────────")
    print("  Keyboard simulates physical gestures.\n")

    game     = SimonSaysGame()
    last_cmd = ""

    threading.Thread(target=_terminal_listener, daemon=True).start()

    # Start immediately
    game.start()

    try:
        while not _quit_flag.is_set():

            # Drain input queue
            with _input_lock:
                commands = list(_input_queue)
                _input_queue.clear()

            for cmd in commands:
                last_cmd = cmd
                if cmd == "q":
                    _quit_flag.set()
                    break
                elif cmd == "r":
                    game.start()
                elif cmd == "h":
                    # Print full history inline (will be overwritten next render)
                    for entry in game.history:
                        print(f"    {entry}")
                elif cmd == "w":
                    game.submit_action(ACTION_WAVE)
                elif cmd == "c":
                    game.submit_action(ACTION_CLAP)
                elif cmd == "s":
                    game.submit_action(ACTION_SHH)
                elif cmd == "n":
                    game.submit_action(None)

            snap = game.tick()
            _render(snap, last_cmd)
            time.sleep(0.05)   # 20 fps render loop

    except KeyboardInterrupt:
        pass

    print("\n  Thanks for playing!\n")


if __name__ == "__main__":
    main()