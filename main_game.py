"""
Simon Says — Full Integrated Game (WAVE + CLAP + MEOW, no SHH)
"""

import sys
import os
import time
import threading
import cv2
import numpy as np

from src.gesture.camera   import CameraStream
from src.gesture.detector import WaveDetector
from src.audio.detector   import AudioDetector
from src.audio.speech     import SpeechDetector
from src.game.logic       import SimonSaysGame
from src.game.constants   import (
    STATE_IDLE, STATE_COUNTDOWN, STATE_PLAYING,
    STATE_WAITING, STATE_FEEDBACK, STATE_GAME_OVER,
    ACTION_WAVE, ACTION_CLAP, ACTION_MEOW,
    STARTING_LIVES,
)

_quit_flag = threading.Event()
_key_queue = []
_key_lock  = threading.Lock()

RS="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
GR="\033[92m"; YE="\033[93m"; CY="\033[96m"
RE="\033[91m"


def _terminal_listener():
    print(f"  {DIM}Keyboard: w=wave  c=clap  m=meow  r=restart  q=quit{RS}")
    while not _quit_flag.is_set():
        try:
            cmd = input().strip().lower()
        except EOFError:
            break
        with _key_lock:
            _key_queue.append(cmd)


# ══════════════════════════════════════════════════════════════════════
#  Drawing helpers
# ══════════════════════════════════════════════════════════════════════

def _put(img, text, x, y, color=(255,255,255), scale=0.65, thick=2, shadow=True):
    font = cv2.FONT_HERSHEY_DUPLEX
    if shadow:
        cv2.putText(img, text, (x+1,y+1), font, scale, (0,0,0), thick+1, cv2.LINE_AA)
    cv2.putText(img, text, (x,y), font, scale, color, thick, cv2.LINE_AA)


def _draw_lives(img, lives, max_lives, x, y):
    for i in range(max_lives):
        color = (50, 50, 220) if i < lives else (60, 60, 60)
        cv2.circle(img, (x + i*24, y), 9, color,        -1, cv2.LINE_AA)
        cv2.circle(img, (x + i*24, y), 9, (255,255,255),  1, cv2.LINE_AA)


def _draw_audio_bar(img, rms, x, y):
    bar_w = 80; bar_h = 6
    rms_w = int(min(rms / 0.15, 1.0) * bar_w)
    cv2.rectangle(img, (x, y), (x+bar_w, y+bar_h), (40,40,40),  -1)
    cv2.rectangle(img, (x, y), (x+rms_w, y+bar_h), (0,180,255), -1)
    _put(img, "VOL", x+bar_w+5, y+bar_h, (120,120,120), scale=0.35, thick=1, shadow=False)


def _panel(img, x, y, w, h, alpha=0.6):
    sub   = img[y:y+h, x:x+w]
    black = np.zeros_like(sub)
    cv2.addWeighted(black, alpha, sub, 1-alpha, 0, sub)
    img[y:y+h, x:x+w] = sub


def draw_hud(frame, snap, audio, speech, wave_active):
    out   = frame.copy()
    H, W  = out.shape[:2]
    state = snap["state"]

    # ── Top bar ────────────────────────────────────────────────────────
    _panel(out, 0, 0, W, 56)
    _put(out, "SIMON SAYS", 12, 32, (0,220,255), scale=0.85, thick=2)
    _put(out, f"Score: {snap['score']}", W-160, 22, (255,255,255), scale=0.65)
    if snap["streak"] >= 2:
        _put(out, f"x{snap['streak']} streak!", W-160, 44, (0,255,160), scale=0.55)
    _put(out, snap["difficulty"], W//2-30, 22, (180,180,180), scale=0.55, thick=1)
    _put(out, f"Round {snap['round']}", W//2-35, 42, (140,140,140), scale=0.5, thick=1)

    # ── Lives ──────────────────────────────────────────────────────────
    lives_panel_w = STARTING_LIVES * 24 + 20
    _panel(out, 0, H-46, lives_panel_w, 46)
    _draw_lives(out, snap["lives"], snap["max_lives"], 14, H-20)

    # ── Audio meter ────────────────────────────────────────────────────
    _panel(out, W-105, H-38, 105, 38)
    _draw_audio_bar(out, audio["rms"], W-100, H-28)

    # ── Hand visible dot ───────────────────────────────────────────────
    hc = (0,255,80) if snap.get("_hand_visible") else (80,80,80)
    cv2.circle(out, (W-20, 70), 7, hc, -1, cv2.LINE_AA)
    _put(out, "CAM", W-52, 75, (160,160,160), scale=0.4, thick=1, shadow=False)

    # ── Speech last heard ──────────────────────────────────────────────
    last = speech.get("last_heard", "")
    if last and (time.time() - getattr(draw_hud, "_lh_ts", 0)) < 2.0:
        _put(out, f'heard: "{last}"', 12, H-58,
             (180,180,180), scale=0.45, thick=1)
    if speech.get("_last_heard_updated"):
        draw_hud._lh_ts = time.time()

    # ── Centre panel ───────────────────────────────────────────────────
    if state == STATE_COUNTDOWN:
        n   = int(snap["countdown_left"]) + 1
        txt = str(min(n, 3))
        _panel(out, W//2-80, H//2-60, 160, 90)
        cv2.putText(out, txt, (W//2-35, H//2+22),
                    cv2.FONT_HERSHEY_DUPLEX, 2.8, (0,220,255), 4, cv2.LINE_AA)
        _put(out, "Get ready!", W//2-60, H//2+55, (200,200,200), scale=0.65)

    elif state in (STATE_PLAYING, STATE_WAITING):
        req      = snap["action_required"]
        is_simon = snap["simon_says"]

        _panel(out, 20, H//2-65, W-40, 125)

        if is_simon:
            _put(out, "Simon says", W//2-100, H//2-30, (200,200,200), scale=0.7)
            cv2.putText(out, req.upper()+"!",
                        (W//2-110, H//2+30),
                        cv2.FONT_HERSHEY_DUPLEX, 1.4, (0,255,120), 3, cv2.LINE_AA)
        else:
            _put(out, "TRAP:", W//2-40, H//2-30, (80,80,255), scale=0.7)
            cv2.putText(out, req.upper()+"!",
                        (W//2-110, H//2+30),
                        cv2.FONT_HERSHEY_DUPLEX, 1.4, (0,80,255), 3, cv2.LINE_AA)

        # 3 action hints
        hints  = [
            (ACTION_WAVE, "👋 WAVE"),
            (ACTION_CLAP, "👏 CLAP"),
            (ACTION_MEOW, "🐱 MEOW"),
        ]
        slot_w = (W - 40) // 3
        for i, (act, label) in enumerate(hints):
            hx   = 30 + i * slot_w
            hcol = (0,255,120) if (act == req and is_simon) else (80,80,80)
            _put(out, label, hx, H//2+62, hcol, scale=0.58, thick=1)

    elif state == STATE_FEEDBACK:
        res   = snap["last_result"]
        color = (0,255,120) if res["is_positive"] else (0,80,255)
        _panel(out, 20, H//2-55, W-40, 110)
        msg = res["message"]
        tx  = max(20, W//2 - len(msg)*8)
        cv2.putText(out, msg, (tx, H//2+10),
                    cv2.FONT_HERSHEY_DUPLEX, 0.85, color, 2, cv2.LINE_AA)
        if res["points"]:
            _put(out, f"+{res['points']} pts", W//2-35, H//2+50,
                 (0,255,160), scale=0.75, thick=2)

    elif state == STATE_GAME_OVER:
        _panel(out, 20, H//2-90, W-40, 185)
        cv2.putText(out, "GAME OVER", (W//2-135, H//2-28),
                    cv2.FONT_HERSHEY_DUPLEX, 1.6, (0,60,255), 3, cv2.LINE_AA)
        _put(out, f"Final Score: {snap['score']}", W//2-100, H//2+20,
             (255,255,255), scale=0.8, thick=2)
        _put(out, f"Rounds: {snap['round']}", W//2-55, H//2+50,
             (180,180,180), scale=0.65)
        _put(out, "Press R to play again", W//2-115, H//2+82,
             (0,220,255), scale=0.62)

    # ── Event border flashes ───────────────────────────────────────────
    if wave_active:
        cv2.rectangle(out, (0,0), (W,H), (0,255,120), 5)
        _put(out, "WAVE!", W//2-50, H-70, (0,255,120), scale=1.1, thick=3)
    if audio.get("clap"):
        cv2.rectangle(out, (0,0), (W,H), (0,160,255), 5)
        _put(out, "CLAP!", W//2-50, H-70, (0,180,255), scale=1.0, thick=3)
    if speech.get("meow"):
        cv2.rectangle(out, (0,0), (W,H), (255,180,0), 5)
        _put(out, "MEOW!", W//2-55, H-70, (255,200,0), scale=1.1, thick=3)

    return out


# ══════════════════════════════════════════════════════════════════════
#  Terminal logger
# ══════════════════════════════════════════════════════════════════════

def _bar(v, mx, w=14):
    f = int(min(v/max(mx,1e-6),1.0)*w)
    return "█"*f + "░"*(w-f)

def log_frame(snap, audio, fps):
    state = snap["state"]
    clr   = GR if snap["lives"]==STARTING_LIVES else YE if snap["lives"]>=3 else RE
    lives_str = "❤ "*snap["lives"] + "  "*(snap["max_lives"]-snap["lives"])
    print(
        f"\r  {DIM}[{state:<10}]{RS} "
        f"{clr}{lives_str}{RS}"
        f"Sc:{BOLD}{snap['score']:>4}{RS} "
        f"VOL[{_bar(audio['rms'],0.15)}] "
        f"{DIM}{fps:.0f}fps{RS}   ",
        end="", flush=True
    )


# ══════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════

def main():
    print(f"\n  {BOLD}{CY}🎮  Simon Says — Starting up...{RS}\n")

    # Camera
    cam = CameraStream(device_index=0, width=640, height=480)
    try:
        cam.start()
        print(f"  {GR}✅  Camera ready{RS}")
    except RuntimeError as e:
        print(f"  {RE}❌  Camera: {e}{RS}"); sys.exit(1)

    # Wave
    wave_detector = WaveDetector(
        buffer_size=30, reversal_thresh=3,
        time_window=1.5, cooldown=1.5,
    )

    # Clap only (no shh)
    audio_detector = AudioDetector(
        spike_thresh=0.0218, spike_ratio=6.2,
        shh_thresh=999.0,          # effectively disabled
        shh_min_duration=999.0,    # effectively disabled
        clap_cooldown=0.6,
        shh_cooldown=999.0,
    )
    try:
        audio_detector.start()
        print(f"  {GR}✅  Microphone ready (clap){RS}")
    except Exception as e:
        print(f"  {RE}❌  Microphone: {e}{RS}"); sys.exit(1)

    # Meow
    speech_detector = SpeechDetector(cooldown=1.5, target_word="meow")
    try:
        speech_detector.start()
        print(f"  {GR}✅  Speech ready (meow){RS}")
    except Exception as e:
        print(f"  {RE}❌  Speech: {e}{RS}"); sys.exit(1)

    # Game
    game = SimonSaysGame()
    game.start()
    print(f"  {GR}✅  Game engine ready{RS}")
    print(f"\n  {YE}👋 Wave  👏 Clap  🐱 Say MEOW{RS}")
    print(f"  {DIM}Keyboard: w=wave  c=clap  m=meow  r=restart  q=quit{RS}\n")

    threading.Thread(target=_terminal_listener, daemon=True).start()

    WIN = "Simon Says  |  Q=quit  R=restart"
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)

    fps_counter = 0
    fps_start   = time.time()
    current_fps = 30.0

    wave_flash_until = 0.0
    clap_flash_until = 0.0
    meow_flash_until = 0.0

    audio_result  = {"clap":False,"shh":False,"rms":0.0,"band_rms":0.0,"shh_active":False}
    speech_result = {"meow":False,"last_heard":""}
    prev_last_heard = ""

    while not _quit_flag.is_set():
        now = time.time()

        # ── Sensors ────────────────────────────────────────────────────
        raw_frame = cam.get_frame()
        if raw_frame is None:
            continue

        gesture_result  = wave_detector.process(raw_frame)
        annotated_frame = gesture_result["annotated"]
        audio_result    = audio_detector.update()
        speech_result   = speech_detector.update()

        new_heard = speech_result["last_heard"]
        speech_result["_last_heard_updated"] = (
            new_heard != prev_last_heard and bool(new_heard)
        )
        prev_last_heard = new_heard

        # ── Flash timers ───────────────────────────────────────────────
        if gesture_result["wave"]: wave_flash_until = now + 0.6
        if audio_result["clap"]:   clap_flash_until = now + 0.6
        if speech_result["meow"]:  meow_flash_until = now + 0.6

        wave_active   = now < wave_flash_until
        audio_display = {**audio_result, "clap": now < clap_flash_until}
        speech_display= {**speech_result, "meow": now < meow_flash_until}

        # ── Submit to game ─────────────────────────────────────────────
        if gesture_result["wave"]: game.submit_action(ACTION_WAVE)
        if audio_result["clap"]:   game.submit_action(ACTION_CLAP)
        if speech_result["meow"]:  game.submit_action(ACTION_MEOW)

        # ── Keyboard fallback ──────────────────────────────────────────
        with _key_lock:
            cmds = list(_key_queue); _key_queue.clear()
        for cmd in cmds:
            if   cmd == "q": _quit_flag.set()
            elif cmd == "r": game.start()
            elif cmd == "w": game.submit_action(ACTION_WAVE)
            elif cmd == "c": game.submit_action(ACTION_CLAP)
            elif cmd == "m": game.submit_action(ACTION_MEOW)
            elif cmd == "n": game.submit_action(None)

        # ── Tick + render ──────────────────────────────────────────────
        snap = game.tick()
        snap["_hand_visible"] = gesture_result["hand_visible"]

        hud_frame = draw_hud(
            annotated_frame, snap,
            audio_display, speech_display, wave_active
        )

        fps_counter += 1
        if (now - fps_start) >= 1.0:
            current_fps = fps_counter / (now - fps_start)
            fps_counter = 0
            fps_start   = now

        cv2.imshow(WIN, hud_frame)
        log_frame(snap, audio_result, current_fps)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):  _quit_flag.set()
        elif key == ord("r"):      game.start()
        elif key == ord("w"):      game.submit_action(ACTION_WAVE)
        elif key == ord("c"):      game.submit_action(ACTION_CLAP)
        elif key == ord("m"):      game.submit_action(ACTION_MEOW)

    # ── Cleanup ────────────────────────────────────────────────────────
    print(f"\n\n  {DIM}Shutting down...{RS}")
    wave_detector.close()
    audio_detector.stop()
    speech_detector.stop()
    cam.stop()
    cv2.destroyAllWindows()
    print(f"  {GR}Done. Final score: {game.score}{RS}\n")


if __name__ == "__main__":
    main()
