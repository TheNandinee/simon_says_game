"""
Audio Detector Module (false-trigger hardened)
"""

import time
import queue
import collections
import numpy as np
import sounddevice as sd
from scipy.signal import butter, sosfilt


def _make_bandpass(low_hz, high_hz, fs, order=4):
    nyq = fs / 2.0
    sos = butter(order, [low_hz / nyq, high_hz / nyq], btype="band", output="sos")
    return sos


def _rms(signal):
    return float(np.sqrt(np.mean(signal ** 2)))


class AudioDetector:
    def __init__(
        self,
        device_index      = 1,
        sample_rate       = 44100,
        chunk_size        = 1024,
        spike_thresh      = 0.08,   # raised: was 0.03 — stops false triggers
        spike_ratio       = 10.0,   # raised: was 6.0  — needs sharper spike
        shh_band          = (1000, 8000),
        shh_thresh        = 0.008,
        shh_min_duration  = 0.3,
        clap_cooldown     = 0.6,    # raised: was 0.4
        shh_cooldown      = 0.8,
        history_secs      = 1.5,
    ):
        self.sample_rate      = sample_rate
        self.chunk_size       = chunk_size
        self.spike_thresh     = spike_thresh
        self.spike_ratio      = spike_ratio
        self.shh_thresh       = shh_thresh
        self.shh_min_duration = shh_min_duration
        self.clap_cooldown    = clap_cooldown
        self.shh_cooldown     = shh_cooldown
        self.device_index     = device_index

        self._sos = _make_bandpass(shh_band[0], shh_band[1], sample_rate)

        history_chunks = max(1, int(history_secs * sample_rate / chunk_size))
        self._rms_history = collections.deque([0.0] * history_chunks, maxlen=history_chunks)

        self._shh_start       = None
        self._last_clap_time  = 0.0
        self._last_shh_time   = 0.0

        self.clap_detected    = False
        self.shh_detected     = False
        self.current_rms      = 0.0
        self.current_band_rms = 0.0
        self.shh_active       = False

        self._audio_queue = queue.Queue(maxsize=50)
        self._stream      = None
        self._running     = False

    def start(self):
        self._running = True
        self._stream  = sd.InputStream(
            samplerate = self.sample_rate,
            channels   = 1,
            dtype      = "float32",
            blocksize  = self.chunk_size,
            callback   = self._audio_callback,
        )
        self._stream.start()

    def stop(self):
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def is_running(self):
        return self._running

    def update(self) -> dict:
        self.clap_detected = False
        self.shh_detected  = False
        while True:
            try:
                chunk = self._audio_queue.get_nowait()
                self._process_chunk(chunk)
            except queue.Empty:
                break
        return {
            "clap"      : self.clap_detected,
            "shh"       : self.shh_detected,
            "rms"       : self.current_rms,
            "band_rms"  : self.current_band_rms,
            "shh_active": self.shh_active,
        }

    def _audio_callback(self, indata, frames, time_info, status):
        if not self._running:
            return
        try:
            self._audio_queue.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass

    def _process_chunk(self, chunk):
        now = time.time()
        rms = _rms(chunk)
        self.current_rms = rms

        avg_rms = float(np.mean(self._rms_history)) if self._rms_history else 0.0
        self._rms_history.append(rms)

        if (
            rms > self.spike_thresh
            and avg_rms > 0
            and (rms / (avg_rms + 1e-9)) > self.spike_ratio
            and (now - self._last_clap_time) > self.clap_cooldown
        ):
            self.clap_detected   = True
            self._last_clap_time = now
            self._shh_start      = None

        filtered  = sosfilt(self._sos, chunk)
        band_rms  = _rms(filtered)
        self.current_band_rms = band_rms

        if band_rms > self.shh_thresh:
            self.shh_active = True
            if self._shh_start is None:
                self._shh_start = now
            elif (
                (now - self._shh_start) >= self.shh_min_duration
                and (now - self._last_shh_time) > self.shh_cooldown
            ):
                self.shh_detected   = True
                self._last_shh_time = now
                self._shh_start     = None
        else:
            self.shh_active = False
            self._shh_start = None
