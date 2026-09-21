"""Real audio I/O: live microphone level and spoken replies.

Everything here is optional. If a library, device or speech engine is
missing, callers get an exception or ``None`` and fall back to the
simulators in ``voice.py``.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass

try:
    import numpy as np
    import sounddevice as sd
except (ImportError, OSError):  # not installed, or PortAudio missing
    np = sd = None


def available() -> bool:
    return sd is not None


class LiveMic:
    """Opens the default input device and exposes a 0-1 loudness level.

    The level is measured above an adaptive noise floor (a low percentile of
    the last few seconds), so a noisy room still reads as silence.
    """

    HISTORY_BLOCKS = 400     # ~4 s of 10 ms blocks
    HEADROOM_DB = 5.0        # ignore wobble just above the floor
    RANGE_DB = 25.0          # floor + headroom + range == full level

    def __init__(self) -> None:
        self.level = 0.0
        self._stream = None
        self._history: list[float] = []

    def start(self) -> None:
        if sd is None:
            raise RuntimeError("sounddevice is not installed")
        self.level = 0.0
        self._history = []
        rate = int(sd.query_devices(kind="input")["default_samplerate"])
        self._stream = sd.InputStream(samplerate=rate, channels=1, blocksize=rate // 100,
                                      callback=self._on_audio)
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self.level = 0.0

    def _on_audio(self, data, frames, time_info, status) -> None:
        rms = float(np.sqrt(np.mean(np.square(data))))
        db = 20.0 * math.log10(rms + 1e-9)
        if db > -80.0:  # skip digital silence some mics emit while gating
            self._history.append(db)
            del self._history[:-self.HISTORY_BLOCKS]
        if len(self._history) < 20:
            self.level = 0.0
            return
        floor = float(np.percentile(self._history, 20))
        self.level = min(1.0, max(0.0, (db - floor - self.HEADROOM_DB) / self.RANGE_DB))


@dataclass
class Utterance:
    samples: "np.ndarray"   # float32, mono
    rate: int
    envelope: "np.ndarray"  # loudness 0-1 per 10 ms frame

    @property
    def duration(self) -> float:
        return len(self.samples) / self.rate

    def level_at(self, seconds: float) -> float:
        i = int(seconds * 100)
        return float(self.envelope[i]) if 0 <= i < len(self.envelope) else 0.0


def synthesize(text: str, voice_hint: str = "", rate: int = 1) -> Utterance | None:
    """Render ``text`` to audio with the OS speech engine. Blocking; run it off the UI thread."""
    if sd is None:
        return None
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        if sys.platform == "win32":
            _windows_tts(text, path, voice_hint, rate)
        elif exe := (shutil.which("espeak-ng") or shutil.which("espeak")):
            subprocess.run([exe, "-w", path, text], check=True, timeout=30, capture_output=True)
        else:
            return None
        return _load_wav(path)
    except Exception:
        return None
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _windows_tts(text: str, path: str, voice_hint: str, rate: int) -> None:
    def quote(s: str) -> str:
        return "'" + s.replace("'", "''") + "'"

    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"$v = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Name -like {quote('*' + voice_hint + '*')} }}"
        " | Select-Object -First 1;"
        "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) };"
        f"$s.Rate = {int(rate)};"
        f"$s.SetOutputToWaveFile({quote(path)});"
        f"$s.Speak({quote(text)});"
        "$s.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                   check=True, timeout=30, capture_output=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _load_wav(path: str) -> Utterance:
    with wave.open(path, "rb") as wav:
        rate, width, channels = wav.getframerate(), wav.getsampwidth(), wav.getnchannels()
        raw = wav.readframes(wav.getnframes())
    if width == 1:
        samples = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
    else:
        dtype = {2: np.int16, 4: np.int32}[width]
        samples = np.frombuffer(raw, dtype).astype(np.float32) / float(2 ** (8 * width - 1))
    samples = samples.reshape(-1, channels).mean(axis=1).astype(np.float32)

    hop = max(1, rate // 100)
    frames = samples[: len(samples) // hop * hop].reshape(-1, hop)
    rms = np.sqrt(np.mean(np.square(frames), axis=1))
    envelope = np.clip(rms / max(float(np.percentile(rms, 95)), 1e-6), 0.0, 1.0) ** 0.8
    return Utterance(samples, rate, envelope)


def play(utterance: Utterance) -> None:
    sd.play(utterance.samples, utterance.rate)


def stop_playback() -> None:
    if sd is not None:
        try:
            sd.stop()
        except Exception:
            pass
