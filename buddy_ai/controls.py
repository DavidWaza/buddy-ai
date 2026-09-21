"""Custom-painted controls: round icon buttons, the mic button, model pill, toast."""

from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QMenu, QWidget

from .voice import approach

TAU = math.tau


def ui_font(size: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont()
    font.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", "Arial"])
    font.setPointSizeF(size)
    font.setWeight(weight)
    return font


def draw_icon(p: QPainter, name: str, c: QPointF, size: float, color: QColor) -> None:
    """Line icons drawn in a ``size`` x ``size`` box centred on ``c``."""
    s = size / 2
    pen = QPen(color, max(1.6, size * 0.085))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    x, y = c.x(), c.y()

    if name == "menu":
        for dy, right in ((-0.55, 0.72), (0.0, 0.72), (0.55, 0.3)):
            p.drawLine(QPointF(x - 0.72 * s, y + dy * s), QPointF(x + right * s, y + dy * s))
    elif name == "plus":
        p.drawLine(QPointF(x - 0.75 * s, y), QPointF(x + 0.75 * s, y))
        p.drawLine(QPointF(x, y - 0.75 * s), QPointF(x, y + 0.75 * s))
    elif name == "close":
        k = 0.6 * s
        p.drawLine(QPointF(x - k, y - k), QPointF(x + k, y + k))
        p.drawLine(QPointF(x - k, y + k), QPointF(x + k, y - k))
    elif name == "gear":
        teeth, ro, ri = 8, 0.92 * s, 0.68 * s
        step = TAU / teeth
        path = QPainterPath()
        for k in range(teeth):
            base = k * step
            for off, r in ((-0.30, ri), (-0.16, ro), (0.16, ro), (0.30, ri)):
                pt = QPointF(x + math.cos(base + off * step) * r, y + math.sin(base + off * step) * r)
                if path.elementCount() == 0:
                    path.moveTo(pt)
                else:
                    path.lineTo(pt)
        path.closeSubpath()
        p.drawPath(path)
        p.drawEllipse(c, 0.3 * s, 0.3 * s)
    elif name == "mic":
        p.drawRoundedRect(QRectF(x - 0.32 * s, y - 0.95 * s, 0.64 * s, 1.15 * s), 0.32 * s, 0.32 * s)
        arc = QPainterPath()
        arc.arcMoveTo(QRectF(x - 0.62 * s, y - 0.55 * s, 1.24 * s, 1.1 * s), 180)
        arc.arcTo(QRectF(x - 0.62 * s, y - 0.55 * s, 1.24 * s, 1.1 * s), 180, 180)
        p.drawPath(arc)
        p.drawLine(QPointF(x, y + 0.55 * s), QPointF(x, y + 0.92 * s))
    elif name == "updown":
        k = 0.34 * s
        p.drawPolyline([QPointF(x - k, y - 0.25 * s), QPointF(x, y - 0.25 * s - k), QPointF(x + k, y - 0.25 * s)])
        p.drawPolyline([QPointF(x - k, y + 0.25 * s), QPointF(x, y + 0.25 * s + k), QPointF(x + k, y + 0.25 * s)])


class PressableWidget(QWidget):
    """Base for painted buttons: hover/press animation and a click signal."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.hover = 0.0
        self.press = 0.0
        self._pressed = False
        self._hover_anim = self._make_anim("hover", 160)
        self._press_anim = self._make_anim("press", 110)

    def _make_anim(self, attr: str, duration: int) -> QVariantAnimation:
        anim = QVariantAnimation(self)
        anim.setDuration(duration)

        def apply(value):
            setattr(self, attr, float(value))
            self.update()

        anim.valueChanged.connect(apply)
        return anim

    @staticmethod
    def _run(anim: QVariantAnimation, start: float, end: float) -> None:
        anim.stop()
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.start()

    def hit(self, pos: QPointF) -> bool:
        return self.rect().contains(pos.toPoint())

    def enterEvent(self, event) -> None:
        self._run(self._hover_anim, self.hover, 1.0)

    def leaveEvent(self, event) -> None:
        self._run(self._hover_anim, self.hover, 0.0)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.hit(event.position()):
            self._pressed = True
            self._run(self._press_anim, self.press, 1.0)

    def mouseReleaseEvent(self, event) -> None:
        if not self._pressed:
            return
        self._pressed = False
        self._run(self._press_anim, self.press, 0.0)
        if self.hit(event.position()):
            self.clicked.emit()


class CircleButton(PressableWidget):
    def __init__(self, icon: str, diameter: int = 54, light: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.icon = icon
        self.light = light
        self.setFixedSize(diameter + 4, diameter + 4)

    def hit(self, pos: QPointF) -> bool:
        c = QPointF(self.width() / 2, self.height() / 2)
        return math.hypot(pos.x() - c.x(), pos.y() - c.y()) <= self.width() / 2

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        r = (self.width() / 2 - 2) * (1 - 0.07 * self.press)
        h = self.hover
        if self.light:
            fill = QColor(int(238 + 17 * h), int(234 + 21 * h), int(228 + 27 * h))
            border, icon = QColor(255, 255, 255, 90), QColor(30, 30, 30)
        else:
            v = int(34 + 16 * h)
            fill = QColor(v, v, v, 235)
            border, icon = QColor(255, 255, 255, int(28 + 30 * h)), QColor(236, 236, 236)
        p.setPen(QPen(border, 1.0))
        p.setBrush(fill)
        p.drawEllipse(c, r, r)
        draw_icon(p, self.icon, c, r * 0.72, icon)


class MicButton(PressableWidget):
    """Big glowing mic. Reacts to the live level while listening."""

    DIAMETER = 92

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(190, 190)
        self._t = 0.0
        self._active = 0.0
        self._glow = 0.0

    def hit(self, pos: QPointF) -> bool:
        c = QPointF(self.width() / 2, self.height() / 2)
        return math.hypot(pos.x() - c.x(), pos.y() - c.y()) <= self.DIAMETER / 2 + 4

    def advance(self, dt: float, active: bool, level: float) -> None:
        self._t += dt
        self._active = approach(self._active, 1.0 if active else 0.0, 8.0, dt)
        self._glow = approach(self._glow, (0.35 + 0.65 * level) if active else 0.0, 12.0, dt)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        r = self.DIAMETER / 2 * (1 - 0.06 * self.press)
        a, g, h = self._active, self._glow, self.hover
        p.setPen(Qt.PenStyle.NoPen)

        # Outer glow.
        glow_r = r * (1.35 + 0.55 * g)
        grad = QRadialGradient(c, glow_r)
        grad.setColorAt(0.55, QColor(80, 140, 230, int(40 + 110 * g + 25 * h)))
        grad.setColorAt(1.0, QColor(80, 140, 230, 0))
        p.setBrush(grad)
        p.drawEllipse(c, glow_r, glow_r)

        # Expanding pulse rings while listening.
        if a > 0.01:
            p.setBrush(Qt.BrushStyle.NoBrush)
            for k in range(2):
                phase = (self._t * 0.9 + k * 0.5) % 1.0
                rr = r + 4 + phase * 34
                p.setPen(QPen(QColor(150, 190, 255, int(a * 150 * (1 - phase) ** 2)), 1.5))
                p.drawEllipse(c, rr, rr)
            p.setPen(Qt.PenStyle.NoPen)

        # Body.
        body = QRadialGradient(QPointF(c.x(), c.y() - r * 0.4), r * 1.4)
        body.setColorAt(0.0, QColor(int(38 + 30 * a + 10 * h), int(64 + 45 * a + 10 * h), int(100 + 60 * a + 12 * h)))
        body.setColorAt(1.0, QColor(int(18 + 14 * a), int(32 + 26 * a), int(54 + 40 * a)))
        p.setBrush(body)
        p.setPen(QPen(QColor(110, 160, 230, int(110 + 100 * a)), 1.4))
        p.drawEllipse(c, r, r)
        draw_icon(p, "mic", c, r * 0.72, QColor(240, 244, 250))


class ModelPill(PressableWidget):
    model_changed = Signal(str)

    def __init__(self, models: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.models = models
        self.current = models[0]
        self.setFixedSize(140, 58)
        self.clicked.connect(self._open_menu)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        k = 1 - 0.04 * self.press
        w, h = (self.width() - 4) * k, (self.height() - 4) * k
        rect = QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)
        h_ = self.hover
        p.setPen(QPen(QColor(255, 255, 255, int(30 + 30 * h_)), 1.0))
        p.setBrush(QColor(int(36 + 14 * h_), int(44 + 14 * h_), int(56 + 14 * h_), 225))
        p.drawRoundedRect(rect, h / 2, h / 2)

        p.setFont(ui_font(12.5))
        fm = p.fontMetrics()
        text_w = fm.horizontalAdvance(self.current)
        total = text_w + 12 + 16
        x0 = rect.center().x() - total / 2
        p.setPen(QColor(236, 238, 242))
        p.drawText(QRectF(x0, rect.top(), text_w + 2, rect.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.current)
        draw_icon(p, "updown", QPointF(x0 + text_w + 12 + 8, rect.center().y()), 16, QColor(220, 224, 230))

    def _open_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #232830; color: #eceef2; border: 1px solid #3a414c;"
            " border-radius: 12px; padding: 6px; }"
            "QMenu::item { padding: 8px 26px 8px 14px; border-radius: 8px; }"
            "QMenu::item:selected { background: #34404f; }"
            "QMenu::indicator { width: 0; }")
        group = QActionGroup(menu)
        for model in self.models:
            action = QAction(("✓  " if model == self.current else "    ") + model, menu)
            action.setData(model)
            group.addAction(action)
            menu.addAction(action)
        height = menu.sizeHint().height()
        chosen = menu.exec(self.mapToGlobal(QPoint(8, -height - 6)))
        if chosen and chosen.data() != self.current:
            self.current = chosen.data()
            self.update()
            self.model_changed.emit(self.current)


class Toast(QLabel):
    """A small message that fades in near the top and fades away."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFont(ui_font(10.5))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: rgba(44, 44, 46, 235); color: #eeeeee;"
                           " border: 1px solid rgba(255,255,255,30); border-radius: 15px; padding: 7px 16px;")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(220)
        self._hide_timer = QTimer(self, singleShot=True, interval=1700)
        self._hide_timer.timeout.connect(lambda: self._fade_to(0.0))
        self.hide()

    def show_message(self, text: str) -> None:
        self.setText(text)
        self.adjustSize()
        parent = self.parentWidget()
        self.move((parent.width() - self.width()) // 2, 108)
        self.show()
        self.raise_()
        self._fade_to(1.0)
        self._hide_timer.start()

    def _fade_to(self, value: float) -> None:
        self._fade.stop()
        self._fade.setStartValue(self._effect.opacity())
        self._fade.setEndValue(value)
        self._fade.start()
