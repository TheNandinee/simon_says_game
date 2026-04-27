import os, json, queue, threading, time
import sounddevice as sd
from vosk import Model, KaldiRecognizer, SetLogLevel

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "models", "vosk-en")

MEOW_VARIANTS = {"meow", "miao", "miaow", "mew", "meo", "miyow", "myow"}
CLAP_VARIANTS = {"clap", "clapping", "clapped", "klap"}

def _is_meow(text):
    words = {w.strip(".,!?") for w in text.strip().lower().split()}
    return bool(words & MEOW_VARIANTS)

def _is_clap(text):
    words = {w.strip(".,!?") for w in text.strip().lower().split()}
    return bool(words & CLAP_VARIANTS)

class SpeechDetector:
    def __init__(self, sample_rate=16000, cooldown=1.5, target_word="meow", device_index=1):
        self.sample_rate  = sample_rate
        self.cooldown     = cooldown
        self.device_index = device_index
        model_path = os.path.abspath(MODEL_PATH)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Vosk model not found at {model_path}")
        SetLogLevel(-1)
        self._model = Model(model_path)
        self._sample_rate = sample_rate
        self._new_recognizer()
        self._audio_queue  = queue.Queue(maxsize=200)
        self._result_queue = queue.Queue()
        self._stream       = None
        self._thread       = None
        self._running      = False
        self._last_meow_time = 0.0
        self._last_clap_time = 0.0
        self.meow_detected   = False
        self.clap_detected   = False
        self.last_heard      = ""
        self.last_heard_at   = 0.0

    def _new_recognizer(self):
        self._recognizer = KaldiRecognizer(self._model, self._sample_rate)
        self._recognizer.SetWords(True)

    def start(self):
        self._running = True
        self._stream  = sd.RawInputStream(
            device=self.device_index, samplerate=self.sample_rate,
            channels=1, dtype="int16", blocksize=2000,
            callback=self._audio_callback)
        self._stream.start()
        self._thread = threading.Thread(target=self._recognition_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def is_running(self):
        return self._running

    def update(self):
        self.meow_detected = False
        self.clap_detected = False
        while True:
            try:
                text = self._result_queue.get_nowait()
                self.last_heard    = text
                self.last_heard_at = time.time()
                now = time.time()
                if _is_meow(text) and (now - self._last_meow_time) > self.cooldown:
                    self.meow_detected   = True
                    self._last_meow_time = now
                if _is_clap(text) and (now - self._last_clap_time) > self.cooldown:
                    self.clap_detected   = True
                    self._last_clap_time = now
            except queue.Empty:
                break
        return {
            "meow"      : self.meow_detected,
            "clap"      : self.clap_detected,
            "last_heard": self.last_heard,
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
                res  = json.loads(self._recognizer.Result())
                text = res.get("text", "").strip()
                if text:
                    self._result_queue.put(text)
                self._new_recognizer()
            else:
                res  = json.loads(self._recognizer.PartialResult())
                text = res.get("partial", "").strip()
                if text and (_is_meow(text) or _is_clap(text)):
                    self._result_queue.put(text)
