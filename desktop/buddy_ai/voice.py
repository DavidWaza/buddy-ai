"""Conversation state machine.

Listening uses the real microphone level and replies are spoken with the
operating system's text-to-speech (see ``audio.py``). There is no speech
recognition: the reply is a generic one chosen by how much was said. When
live audio is unavailable, ``MicSimulator`` / ``SpeechSimulator`` fake it.
"""

from __future__ import annotations

import math
import random
import re
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from . import audio


class Mode(Enum):
    IDLE = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()


NO_SPEECH_REPLIES = (
    "Hmm, I didn't quite catch that, {name}. Could you say it again?",
    "I'm here and listening, {name}. Whenever you're ready, just speak up.",
)
SHORT_REPLIES = (
    "Got it, {name}! Thanks for letting me know.",
    "Okay, understood. Is there anything else on your mind?",
    "Nice! I hear you loud and clear.",
)
LONG_REPLIES = (
    "Thanks for sharing all of that, {name}. That sounds really thoughtful. Tell me more whenever you like.",
    "I hear you. That's a lot to think about, and you explained it really well.",
    "Great point, {name}. I love where you're going with this. Let's keep talking.",
)


def approach(current: float, target: float, rate: float, dt: float) -> float:
    """Frame-rate independent exponential smoothing."""
    return current + (target - current) * (1.0 - math.exp(-rate * dt))


def count_syllables(word: str) -> int:
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    silent_e = word.rstrip(".,!?;:'\"").endswith("e") and len(groups) > 1
    return max(1, len(groups) - (1 if silent_e else 0))


class MicSimulator:
    """Fakes a microphone level: bursts of talking separated by pauses."""

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng
        self._talking = False
        self._segment_left = rng.uniform(0.3, 0.6)
        self._retarget_in = 0.0
        self._target = 0.0
        self.level = 0.0

    def step(self, dt: float) -> float:
        rng = self._rng
        self._segment_left -= dt
        if self._segment_left <= 0:
            self._talking = not self._talking
            self._segment_left = rng.uniform(0.7, 2.2) if self._talking else rng.uniform(0.25, 0.9)
        self._retarget_in -= dt
        if self._retarget_in <= 0:
            self._retarget_in = rng.uniform(0.05, 0.15)
            self._target = rng.uniform(0.35, 1.0) if self._talking else rng.uniform(0.0, 0.05)
        self.level = approach(self.level, self._target, 20.0, dt)
        return self.level


@dataclass
class TimedWord:
    text: str
    start: float
    end: float
    syllables: int
    peak: float


class SpeechSimulator:
    """Schedules a reply word by word and produces a syllable-shaped level."""

    def __init__(self, text: str, rng: random.Random) -> None:
        self.text = text
        self.words: list[TimedWord] = []
        self._rng = rng
        t = 0.3
        for raw in text.split():
            syllables = count_syllables(raw)
            duration = 0.10 + 0.16 * syllables
            self.words.append(TimedWord(raw, t, t + duration, syllables, rng.uniform(0.6, 1.0)))
            t += duration + 0.05
            if raw[-1] in ",;:":
                t += 0.22
            elif raw[-1] in ".!?":
                t += 0.45
        self.duration = t + 0.2
        self.elapsed = 0.0

    @property
    def done(self) -> bool:
        return self.elapsed >= self.duration

    def step(self, dt: float) -> float:
        self.elapsed += dt
        for word in self.words:
            if word.start <= self.elapsed < word.end:
                progress = (self.elapsed - word.start) / (word.end - word.start)
                phase = (progress * word.syllables) % 1.0
                return word.peak * math.sin(math.pi * phase) ** 0.6 * self._rng.uniform(0.85, 1.0)
        return 0.0

    def word_progress(self) -> list[float]:
        """How far each word has been spoken, in [0, 1]."""
        out = []
        for word in self.words:
            if self.elapsed <= word.start:
                out.append(0.0)
            elif self.elapsed >= word.end:
                out.append(1.0)
            else:
                out.append((self.elapsed - word.start) / (word.end - word.start))
        return out


class SpokenReply(SpeechSimulator):
    """A reply backed by synthesized audio; captions are stretched to fit it."""

    def __init__(self, text: str, rng: random.Random, utterance: audio.Utterance) -> None:
        super().__init__(text, rng)
        self.utterance = utterance
        stretch = utterance.duration / max(self.duration, 1e-6)
        for word in self.words:
            word.start *= stretch
            word.end *= stretch
        self.duration = utterance.duration + 0.25
        self._started_at: float | None = None

    def step(self, dt: float) -> float:
        if self._started_at is None:
            audio.play(self.utterance)
            self._started_at = time.monotonic()
        self.elapsed = time.monotonic() - self._started_at
        return self.utterance.level_at(self.elapsed)

    def stop(self) -> None:
        audio.stop_playback()


class Conversation:
    """IDLE -> LISTENING -> THINKING -> SPEAKING -> IDLE, driven by ``step``."""

    MIN_THINK_SECONDS = (0.7, 1.2)
    MAX_THINK_SECONDS = 12.0
    SPEECH_LEVEL = 0.28      # mic level that counts as talking
    END_OF_TURN_SILENCE = 1.5
    NO_SPEECH_TIMEOUT = 12.0

    def __init__(self, name: str = "friend", seed: int | None = None, live_audio: bool = True) -> None:
        self.name = name
        self.mode = Mode.IDLE
        self.mode_time = 0.0
        self.level = 0.0
        self.speech: SpeechSimulator | None = None
        self.voice_hint = ""
        self.voice_rate = 1
        self._rng = random.Random(seed)
        self._live_mic = audio.LiveMic() if live_audio and audio.available() else None
        self._speak_aloud = live_audio and audio.available()
        self._using_live_mic = False
        self._mic: MicSimulator | None = None
        self._talk_time = 0.0
        self._silence = 0.0
        self._think_left = 0.0
        self._reply_text = ""
        self._pending: Future | None = None
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._last_reply: str | None = None
        self._listeners: list[Callable[[Mode], None]] = []
        self._notice_listeners: list[Callable[[str], None]] = []

    @property
    def using_live_mic(self) -> bool:
        return self._using_live_mic

    def on_mode_changed(self, callback: Callable[[Mode], None]) -> None:
        self._listeners.append(callback)

    def on_notice(self, callback: Callable[[str], None]) -> None:
        self._notice_listeners.append(callback)

    def toggle_mic(self) -> None:
        """Mic tap: start listening, or finish the turn if already listening."""
        self._set_mode(Mode.THINKING if self.mode is Mode.LISTENING else Mode.LISTENING)

    def cancel(self) -> None:
        self._set_mode(Mode.IDLE)

    def shutdown(self) -> None:
        self.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def step(self, dt: float) -> None:
        self.mode_time += dt
        raw = 0.0
        if self.mode is Mode.LISTENING:
            raw = self._live_mic.level if self._using_live_mic else self._mic.step(dt)
            self._track_turn(raw, dt)
        elif self.mode is Mode.THINKING:
            raw = 0.12 + 0.06 * math.sin(self.mode_time * 6.0)
            self._think_left -= dt
            ready = self._pending is None or self._pending.done() or self.mode_time > self.MAX_THINK_SECONDS
            if self._think_left <= 0 and ready:
                self._set_mode(Mode.SPEAKING)
        elif self.mode is Mode.SPEAKING and self.speech:
            raw = self.speech.step(dt)
            if self.speech.done:
                self._set_mode(Mode.IDLE)
        self.level = approach(self.level, raw, 14.0, dt)

    def _track_turn(self, raw: float, dt: float) -> None:
        if raw > self.SPEECH_LEVEL:
            self._talk_time += dt
            self._silence = 0.0
        else:
            self._silence += dt
        if not self._using_live_mic:
            return
        finished_talking = self._talk_time > 0.5 and self._silence > self.END_OF_TURN_SILENCE
        gave_up = self._talk_time < 0.3 and self.mode_time > self.NO_SPEECH_TIMEOUT
        if finished_talking or gave_up:
            self._set_mode(Mode.THINKING)

    def _set_mode(self, mode: Mode) -> None:
        if mode is self.mode:
            return
        self._leave(self.mode)
        self.mode = mode
        self.mode_time = 0.0
        if mode is Mode.LISTENING:
            self._start_listening()
        elif mode is Mode.THINKING:
            self._start_thinking()
        elif mode is Mode.SPEAKING:
            self._start_speaking()
        for callback in self._listeners:
            callback(mode)

    def _leave(self, mode: Mode) -> None:
        if mode is Mode.LISTENING and self._using_live_mic:
            self._live_mic.stop()
            self._using_live_mic = False
        elif mode is Mode.SPEAKING and isinstance(self.speech, SpokenReply):
            self.speech.stop()

    def _start_listening(self) -> None:
        self.speech = None
        self._pending = None
        self._talk_time = self._silence = 0.0
        self._mic = MicSimulator(self._rng)
        if self._live_mic is not None:
            try:
                self._live_mic.start()
                self._using_live_mic = True
            except Exception:
                self._live_mic = None
                self._notice("Microphone unavailable, simulating your voice")

    def _start_thinking(self) -> None:
        self._think_left = self._rng.uniform(*self.MIN_THINK_SECONDS)
        self._reply_text = self._pick_reply()
        self._pending = None
        if self._speak_aloud:
            self._pending = self._executor.submit(
                audio.synthesize, self._reply_text, self.voice_hint, self.voice_rate)

    def _start_speaking(self) -> None:
        utterance, timed_out = None, False
        if self._pending is not None:
            if self._pending.done() and not self._pending.cancelled():
                utterance = self._pending.result()
            else:
                timed_out = True
        self._pending = None
        if utterance is not None:
            self.speech = SpokenReply(self._reply_text, self._rng, utterance)
            return
        if self._speak_aloud and not timed_out:
            self._speak_aloud = False
            self._notice("Text-to-speech unavailable, replying with captions only")
        self.speech = SpeechSimulator(self._reply_text, self._rng)

    def _pick_reply(self) -> str:
        if self._talk_time < 0.3:
            pool = NO_SPEECH_REPLIES
        elif self._talk_time < 2.0:
            pool = SHORT_REPLIES
        else:
            pool = LONG_REPLIES
        options = [r for r in pool if r != self._last_reply]
        self._last_reply = self._rng.choice(options)
        return self._last_reply.format(name=self.name)

    def _notice(self, message: str) -> None:
        for callback in self._notice_listeners:
            callback(message)


