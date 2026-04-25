# 🎮 Simon Says — Physical Gesture Game

> Built for funsies — a fun project for the showcase 🎉

A real-time Simon Says game you play with your **body**, not your keyboard.
Wave your hand, clap loud, or say "meow" — Simon is watching.

---

## 🎯 What It Does

Simon gives you an instruction like **"Simon says WAVE!"** or **"CLAP!"** (trap).
You respond physically in real time:

| Action | How |
|---|---|
| 👋 WAVE | Wave your hand at the camera |
| 👏 CLAP | Clap loudly near your mic |
| 🐱 MEOW | Say "meow" out loud |

Get it right → score points + build streaks.
Fall for a trap → lose a life.
Lose all 5 lives → game over.

---

## 🧠 Tech Stack

| Layer | Tech |
|---|---|
| Camera + Display | OpenCV |
| Hand Tracking | MediaPipe Tasks API (0.10+) |
| Wave Detection | Wrist X oscillation (custom algorithm) |
| Clap Detection | RMS spike detection via SoundDevice + NumPy |
| Meow Detection | Vosk offline speech recognition (no API key needed) |
| Game Logic | Pure Python state machine |
| Language | Python 3.11+ |

---

## 📁 Project Structure
simon_says_game/
├── main_game.py              ← entry point, run this
├── src/
│   ├── gesture/
│   │   ├── camera.py         ← threaded webcam capture
│   │   └── detector.py       ← MediaPipe wave detection
│   ├── audio/
│   │   ├── detector.py       ← clap detection
│   │   └── speech.py         ← meow / vosk speech detection
│   └── game/
│       ├── logic.py          ← Simon Says state machine
│       └── constants.py      ← all tunable game settings
├── tests/
│   ├── test_camera.py        ← test webcam feed
│   ├── test_gesture.py       ← test wave detection live
│   ├── test_audio.py         ← test clap detection live
│   └── test_speech.py        ← test meow detection live
└── models/                   ← Vosk model (downloaded separately)

---

## ⚙️ Setup

### 1. Clone + environment

```bash
git clone https://github.com/YOUR_USERNAME/simon-says-game.git
cd simon-says-game
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Download the Vosk speech model (~50MB, required for MEOW)

```bash
mkdir -p models && cd models
curl -LO https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
mv vosk-model-small-en-us-0.15 vosk-en
rm vosk-model-small-en-us-0.15.zip
cd ..
```

### 3. Calibrate your mic for clap detection

```bash
python3 - << 'CALIBRATE'
import sounddevice as sd, numpy as np, time, re

CHUNK = 1024
print("Stay SILENT for 3s...")
chunks = []
with sd.InputStream(samplerate=44100, channels=1, dtype="float32",
                    blocksize=CHUNK,
                    callback=lambda i,f,t,s: chunks.append(float(np.sqrt(np.mean(i[:,0]**2))))):
    time.sleep(3)
noise = float(np.percentile(chunks, 95))
print(f"Noise floor: {noise:.5f} — now CLAP LOUDLY 3 times (4s)...")
chunks2 = []
with sd.InputStream(samplerate=44100, channels=1, dtype="float32",
                    blocksize=CHUNK,
                    callback=lambda i,f,t,s: chunks2.append(float(np.sqrt(np.mean(i[:,0]**2))))):
    time.sleep(4)
peak         = float(np.percentile(chunks2, 99))
spike_thresh = round(max(noise * 2.5, 0.01), 4)
spike_ratio  = round(max((peak / max(noise, 0.0001)) * 0.35, 2.5), 1)
content      = open("main_game.py").read()
content      = re.sub(r"spike_thresh\s*=\s*[\d.]+", f"spike_thresh={spike_thresh}", content)
content      = re.sub(r"spike_ratio\s*=\s*[\d.]+",  f"spike_ratio={spike_ratio}",  content)
open("main_game.py", "w").write(content)
print(f"✅  Patched → spike_thresh={spike_thresh}, spike_ratio={spike_ratio}")
CALIBRATE
```

### 4. Run the game

```bash
python main_game.py
```

---

## 🕹️ Controls

| Input | Action |
|---|---|
| 👋 Wave at camera | WAVE gesture |
| 👏 Clap near mic | CLAP gesture |
| 🐱 Say "meow" | MEOW gesture |
| `R` in terminal or window | Restart game |
| `Q` / `ESC` in window | Quit |
| `w` / `c` / `m` + Enter | Keyboard fallback for gestures |

---

## 🎮 Game Rules

- Simon gives an instruction every round
- **"Simon says WAVE!"** → you must do it ✅
- **"WAVE!"** (no Simon says) → do NOT do it — it's a trap ⚠️
- Wrong action or falling for a trap → **-1 life**
- You start with **5 lives**
- Game gets faster every 10 correct answers
- Streaks give bonus points 🔥

---

## 🔧 Tuning

All game settings live in `src/game/constants.py`:

```python
STARTING_LIVES          = 5      # number of lives
INSTRUCTION_TIME_EASY   = 8.0    # seconds to respond (easy)
INSTRUCTION_TIME_MEDIUM = 6.0    # seconds to respond (medium)
INSTRUCTION_TIME_HARD   = 4.5    # seconds to respond (hard)
DIFFICULTY_STEP         = 10     # correct answers before harder difficulty
SIMON_SAYS_PROBABILITY  = 0.80   # 80% real, 20% traps
```

---

## 📸 Requirements

- Python 3.10+
- Webcam
- Microphone
- Good lighting for hand detection
- Willingness to look silly saying meow at your laptop 🐱

---

## 🐛 Known Issues

- Vosk small model occasionally mishears background noise as "meow" — say it clearly and it works great
- Wave detection needs decent lighting for MediaPipe to track the hand
- MacBook Air mic is sensitive — run the calibration script if clap isn't triggering

---

## 👩‍💻 Made By

Built by **Nandinee** — for funsies, and because normal portfolio projects are boring.

> *"Why build a CRUD app when you can make your laptop judge you for not meowing loud enough?"*

---

## 📄 License

MIT — do whatever you want with it, just maybe don't use it to cheat at actual Simon Says.
