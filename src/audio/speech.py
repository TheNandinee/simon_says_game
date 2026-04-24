"""
Speech Detector — MEOW only, transcript-reset fix
---------------------------------------------------
Key fix: reset KaldiRecognizer after each final result so the
partial transcript doesn't grow infinitely across sentences.
Only fires on a hardcoded tight list of meow-sound words.
"""

import os
import json
import queue
import threading
import time

import sounddevice as sd
from vosk import Model, KaldiRecognizer, SetLogLevel


MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "models", "vosk-en"
)

# Tight list — only genuine meow transcriptions
MEOW_VARIANTS = {
    "meow", "miao", "miaow", "mew",
    "meo", "miyow", "myow",
}


def _is_meow(text: str) -> bool:
    """Only match if a MEOW_VARIANT appears as a complete word."""
    words = {w.strip(".,!?") for w in text.strip().lower().split()}
    return bool(words & MEOW_VARIANTS)


class SpeechDetector:
    def __init__(self, sample_rate=16000, cooldown=1.5, target_word="meow"):
        self.sample_rate = sample_rate
        self.cooldown    = cooldown

        model_path = os.path.abspath(MODEL_PATH)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Vosk model not found at {model_path}")

        SetLogLevel(-1)
        self._model      = Model(model_path)
        self._sample_rate = sample_rate
        self._new_recognizer()          # creates self._recognizer

        self._audio_queue:  queue.Queue = queue.Queue(maxsize=200)
        self._result_queue: queue.Queue = queue.Queue()

        self._stream   = None
        self._thread   = None
        self._running  = False

        self._last_meow_time: float = 0.0
        self.meow_detected: bool    = False
        self.last_heard: str        = ""
        self.last_heard_at: float   = 0.0

    def _new_recognizer(self):
        """Create a fresh recognizer — clears accumulated transcript."""
        self._recognizer = KaldiRecognizer(self._model, self._sample_rate)
        self._recognizer.SetWords(True)

    def start(self):
        self._running = True
        self._stream  = sd.RawInputStream(
            samplerate = self.sample_rate,
            channels   = 1,
            dtype      = "int16",
            blocksize  = 2000,
            callback   = self._audio_callback,
        )
        self._stream.start()
        self._thread = threading.Thread(
            target=self._recognition_loop, daemon=True
        )
        self._thread.start()

    def stop(self):
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def is_running(self):
        return self._running

    def update(self) -> dict:
        self.meow_detected = False
        while True:
            try:
                text = self._result_queue.get_nowait()
                self.last_heard    = text
                self.last_heard_at = time.time()
                now = time.time()
                if _is_meow(text) and (now - self._last_meow_time) > self.cooldown:
                    self.meow_detected   = True
                    self._last_meow_time = now
            except queue.Empty:
                break
        return {
            "meow"       : self.meow_detected,
            "last_heard" : self.last_heard,
        }

    def _audio_callback(self, indata, frames, time_info, status):
        if not self._running:
            return
        try:
            self._audio_queue.put_nowait(bytes(indata))
        except queue.Full:
            pass

    def _recognition_loop(self):
        while self._running:
            try:
                data = self._audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if self._recognizer.AcceptWaveform(data):
                # ── Final result ──────────────────────────────────────
                res  = json.loads(self._recognizer.Result())
                text = res.get("text", "").strip()
                if text:
                    self._result_queue.put(text)
                # RESET so transcript never accumulates across sentences
                self._new_recognizer()
            else:
                # ── Partial — only queue if it already sounds like meow
                res  = json.loads(self._recognizer.PartialResult())
                text = res.get("partial", "").strip()
                if text and _is_meow(text):
                    self._result_queue.put(text)
