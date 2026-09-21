"""The voice screen: background, buddy, captions and the control bar."""

from __future__ import annotations

import math

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QRadialGradient
from PySide6.QtWidgets import QMainWindow, QWidget

from .buddy import Buddy
from .controls import CircleButton, MicButton, ModelPill, Toast, ui_font
from .voice import Conversation, Mode

BACKGROUND = QColor(22, 22, 22)
TEXT = (234, 229, 220)
TEXT_DIM = (92, 92, 96)
# Each model speaks with its own installed voice (matched by name) and pace.
MODELS = {
    "Waza": ("Zira", 1),
    "Waza Pro": ("David", 0),
    "Waza Mini": ("Hazel", 2),
}


def serif_font(size: float) -> QFont:
    font = QFont()
    font.setFamilies(["Georgia", "Cambria", "Times New Roman", "serif"])
    font.setPointSizeF(size)
    return font


def lerp_color(a: tuple, b: tuple, k: float, alpha: float) -> QColor:
    k = max(0.0, min(1.0, k))
    return QColor(*(int(x + (y - x) * k) for x, y in zip(a, b)), max(0, min(255, int(alpha))))


class VoiceStage(QWidget):
    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name = name
        self.conversation = Conversation(name)
        self.buddy = Buddy()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(360, 640)

        self.menu_button = CircleButton("menu", parent=self)
        self.settings_button = CircleButton("gear", parent=self)
        self.plus_button = CircleButton("plus", diameter=58, parent=self)
        self.close_button = CircleButton("close", diameter=62, light=True, parent=self)
        self.mic_button = MicButton(parent=self)
        self.model_pill = ModelPill(list(MODELS), parent=self)
        self.toast = Toast(self)

        self.mic_button.clicked.connect(self.conversation.toggle_mic)
        self.close_button.clicked.connect(self._on_close)
        self.menu_button.clicked.connect(lambda: self.toast.show_message("Conversation history is coming soon"))
        self.settings_button.clicked.connect(lambda: self.toast.show_message("Settings are coming soon"))
        self.plus_button.clicked.connect(lambda: self.toast.show_message("Attachments are coming soon"))
        self.model_pill.model_changed.connect(self._on_model_changed)
        self.conversation.on_notice(self.toast.show_message)
        self._on_model_changed(self.model_pill.current, announce=False)

        self._caption_cache: tuple | None = None
        self._clock = QElapsedTimer()
        self._clock.start()
        self._last = 0.0
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    # ----------------------------------------------------------------- layout

    def _geometry(self) -> tuple[float, float, float]:
        # Fit buddy + caption block between the top buttons and the mic.
        w, h = self.width(), self.height()
        top, bottom, text_block = 84, h - 208, 120
        free = bottom - top - text_block
        return w / 2, top + free / 2 + 10, min(w * 0.21, free * 0.26)

    def resizeEvent(self, event) -> None:
        w, h = self.width(), self.height()
        margin = 22
        self.menu_button.move(margin, 26)
        self.settings_button.move(w - margin - self.settings_button.width(), 26)
        row_y = h - 44
        self.plus_button.move(margin + 4, int(row_y - self.plus_button.height() / 2))
        self.close_button.move(w - margin - 4 - self.close_button.width(), int(row_y - self.close_button.height() / 2))
        self.model_pill.move(int(w / 2 - self.model_pill.width() / 2), int(row_y - self.model_pill.height() / 2))
        self.mic_button.move(int(w / 2 - self.mic_button.width() / 2), int(h - 162 - self.mic_button.height() / 2))
        self._caption_cache = None

    # ------------------------------------------------------------------ input

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.conversation.toggle_mic()
        elif event.key() == Qt.Key.Key_Escape:
            self.conversation.cancel()
        else:
            super().keyPressEvent(event)

    def _on_model_changed(self, model: str, announce: bool = True) -> None:
        self.conversation.voice_hint, self.conversation.voice_rate = MODELS[model]
        if announce:
            self.toast.show_message(f"Switched to {model}")

    def _on_close(self) -> None:
        if self.conversation.mode is Mode.IDLE:
            self.window().close()
        else:
            self.conversation.cancel()

    # ------------------------------------------------------------------ frame

    def _tick(self) -> None:
        now = self._clock.elapsed() / 1000.0
        dt = min(now - self._last, 0.05)
        self._last = now
        conv = self.conversation
        conv.step(dt)
        self.buddy.step(dt, conv.mode, conv.level)
        listening = conv.mode is Mode.LISTENING
        self.mic_button.advance(dt, listening, conv.level if listening else 0.0)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), BACKGROUND)
        self._paint_bottom_glow(p, w, h)

        cx, cy, R = self._geometry()
        self.buddy.paint(p, cx, cy, R)
        self._paint_texts(p, w, cy + R * 1.85)

    def _paint_bottom_glow(self, p: QPainter, w: int, h: int) -> None:
        wt = self.buddy.weights
        active = 1.0 - wt[Mode.IDLE]
        level = self.buddy.level
        alpha = 95 + 60 * active + 60 * level * (wt[Mode.LISTENING] + wt[Mode.SPEAKING])
        radius = w * (0.95 + 0.1 * active)
        center = QPointF(w / 2, h + 30)
        g = QRadialGradient(center, radius)
        g.setColorAt(0.0, QColor(78, 112, 158, int(alpha)))
        g.setColorAt(0.45, QColor(52, 76, 110, int(alpha * 0.55)))
        g.setColorAt(1.0, QColor(30, 40, 56, 0))
        p.save()
        p.translate(center)
        p.scale(1.0, 0.62)
        p.translate(-center)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(center, radius, radius)
        p.restore()

    def _paint_texts(self, p: QPainter, w: int, y: float) -> None:
        wt = self.buddy.weights
        t = self.buddy.t

        a = wt[Mode.IDLE]
        if a > 0.01:
            p.setFont(serif_font(24))
            p.setPen(QColor(*TEXT, int(255 * a)))
            p.drawText(QRectF(0, y - 6, w, 44), Qt.AlignmentFlag.AlignCenter, f"Let's talk, {self.name}")
            p.setFont(ui_font(10))
            p.setPen(QColor(150, 150, 154, int(200 * a)))
            p.drawText(QRectF(0, y + 42, w, 24), Qt.AlignmentFlag.AlignCenter, "Tap the mic or press Space")

        a = wt[Mode.LISTENING]
        if a > 0.01:
            self._status(p, w, y, "Listening", t, QColor(196, 214, 245, int(255 * a)))
            p.setFont(ui_font(10))
            p.setPen(QColor(140, 146, 158, int(220 * a)))
            p.drawText(QRectF(0, y + 42, w, 24), Qt.AlignmentFlag.AlignCenter,
                       "I'll reply when you pause  ·  Tap the mic to finish"
                       if self.conversation.using_live_mic else
                       "Tap the mic when you're done  ·  Esc to cancel")

        a = wt[Mode.THINKING]
        if a > 0.01:
            self._status(p, w, y, "Thinking", t, QColor(240, 214, 200, int(255 * a)))

        speech = self.conversation.speech
        a = max(wt[Mode.SPEAKING], wt[Mode.IDLE] * (1 - wt[Mode.IDLE])) if speech else 0.0
        if speech and a > 0.01:
            self._captions(p, w, y - 4, speech, a)

    def _status(self, p: QPainter, w: int, y: float, label: str, t: float, color: QColor) -> None:
        p.setFont(ui_font(15))
        p.setPen(color)
        fm = QFontMetricsF(p.font())
        text_w = fm.horizontalAdvance(label)
        x = w / 2 - text_w / 2
        p.drawText(QRectF(x, y, text_w + 4, 36), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
        dots = "." * (int(t * 2.5) % 4)
        p.drawText(QRectF(x + text_w + 1, y, 40, 36), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, dots)

    def _captions(self, p: QPainter, w: int, y: float, speech, alpha: float) -> None:
        font = ui_font(14)
        p.setFont(font)
        fm = QFontMetricsF(font)
        key = (id(speech), w)
        if not self._caption_cache or self._caption_cache[0] != key:
            space = fm.horizontalAdvance(" ")
            max_w = min(w - 64, 520)
            lines, line, line_w = [], [], 0.0
            for i, word in enumerate(speech.words):
                ww = fm.horizontalAdvance(word.text)
                if line and line_w + space + ww > max_w:
                    lines.append((line, line_w))
                    line, line_w = [], 0.0
                line_w += (space if line else 0) + ww
                line.append((i, word.text, ww))
            if line:
                lines.append((line, line_w))
            self._caption_cache = (key, lines, space)
        _, lines, space = self._caption_cache

        progress = speech.word_progress()
        line_h = fm.height() * 1.5
        for row, (line, line_w) in enumerate(lines):
            x = w / 2 - line_w / 2
            baseline = y + fm.ascent() + row * line_h + 8
            for i, text, ww in line:
                k = progress[i]
                lift = (1 - k) * 3 if 0 < k < 1 else 0
                p.setPen(lerp_color(TEXT_DIM, TEXT, math.sqrt(k), 255 * alpha))
                p.drawText(QPointF(x, baseline + lift), text)
                x += ww + space


class MainWindow(QMainWindow):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.setWindowTitle("Buddy AI")
        self.stage = VoiceStage(name, self)
        self.setCentralWidget(self.stage)
        self.stage.setFocus()

    def closeEvent(self, event) -> None:
        self.stage.conversation.shutdown()
        super().closeEvent(event)
