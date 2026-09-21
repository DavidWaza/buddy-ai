"""The buddy: a squishy coral blob with a face, halos, rings and bubbles.

All positions of particles are stored in units of the buddy radius relative
to its centre, so the scene scales cleanly when the window is resized.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient

from .voice import Mode, approach

TAU = math.tau
BLINK_SECONDS = 0.16

INK = (66, 26, 18)
CORAL_LIGHT = (255, 196, 170)
CORAL = (232, 128, 94)
CORAL_DEEP = (176, 76, 50)
LISTEN_BLUE = (150, 188, 255)
SPEAK_WARM = (255, 196, 176)


def rgba(rgb: tuple[int, int, int], alpha: float) -> QColor:
    return QColor(rgb[0], rgb[1], rgb[2], max(0, min(255, int(alpha))))


def blob_path(cx: float, cy: float, rx: float, ry: float, t: float, wobble: float,
              spin: float, points: int = 72) -> QPainterPath:
    """A smooth closed outline whose radius is perturbed by layered sine waves."""
    pts = []
    for i in range(points):
        a = TAU * i / points
        d = (0.55 * math.sin(2 * a + t * 0.9 + spin)
             + 0.45 * math.sin(3 * a - t * 1.4 + 1.7)
             + 0.30 * math.sin(5 * a + t * 2.1 - spin * 0.5)
             + 0.18 * math.sin(7 * a - t * 3.0))
        k = 1.0 + wobble * d
        pts.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))

    def mid(p, q):
        return QPointF((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)

    path = QPainterPath()
    path.moveTo(mid(pts[-1], pts[0]))
    for i, p in enumerate(pts):
        path.quadTo(QPointF(*p), mid(p, pts[(i + 1) % points]))
    path.closeSubpath()
    return path


@dataclass
class Bubble:
    x: float
    y: float
    vx: float
    vy: float
    r: float
    inward: bool
    life: float
    seed: float = field(default_factory=lambda: random.uniform(0, TAU))
    age: float = 0.0
    dead: bool = False

    def alpha(self) -> float:
        fade_in = min(1.0, self.age / 0.2)
        if self.inward:
            dist = math.hypot(self.x, self.y)
            fade_out = max(0.0, min(1.0, (dist - 1.02) / 0.35))
        else:
            fade_out = max(0.0, min(1.0, (self.life - self.age) / (self.life * 0.4)))
        return fade_in * fade_out


@dataclass
class Ring:
    age: float = 0.0
    life: float = 1.4


class Buddy:
    def __init__(self) -> None:
        self.t = 0.0
        self.level = 0.0
        self.weights = {m: (1.0 if m is Mode.IDLE else 0.0) for m in Mode}
        self.bubbles: list[Bubble] = []
        self.rings: list[Ring] = []
        self._rng = random.Random()
        self._spin = 0.0
        self._blink_in = 2.0
        self._blink_t = -1.0
        self._gaze = [0.0, 0.0]
        self._gaze_target = [0.0, 0.0]
        self._gaze_retarget_in = 0.0
        self._emit_in = 0.0
        self._emit_out = 0.0
        self._ring_cooldown = 0.0
        self._last_level = 0.0

    # ------------------------------------------------------------------ update

    def step(self, dt: float, mode: Mode, level: float) -> None:
        rng = self._rng
        self.t += dt
        self.level = level
        for m in Mode:
            self.weights[m] = approach(self.weights[m], 1.0 if m is mode else 0.0, 7.0, dt)
        w = self.weights
        self._spin += dt * (0.4 + 2.2 * w[Mode.THINKING])

        # Blinking, with the occasional double blink.
        if self._blink_t >= 0:
            self._blink_t += dt
            if self._blink_t > BLINK_SECONDS:
                self._blink_t = -1.0
        else:
            self._blink_in -= dt
            if self._blink_in <= 0:
                self._blink_t = 0.0
                self._blink_in = 0.22 if rng.random() < 0.2 else rng.uniform(2.2, 5.5)

        # Where the eyes look.
        t = self.t
        if mode is Mode.THINKING:
            self._gaze_target = [0.6 * math.cos(t * 1.6), -0.6 + 0.25 * math.sin(t * 1.6)]
        elif mode is Mode.LISTENING:
            self._gaze_target = [0.15 * math.sin(t * 0.7), -0.25]
        elif mode is Mode.SPEAKING:
            self._gaze_target = [0.25 * math.sin(t * 0.9), 0.05 * math.sin(t * 1.7)]
        else:
            self._gaze_retarget_in -= dt
            if self._gaze_retarget_in <= 0:
                self._gaze_retarget_in = rng.uniform(1.5, 4.0)
                self._gaze_target = [rng.uniform(-0.6, 0.6), rng.uniform(-0.3, 0.3)]
        for i in (0, 1):
            self._gaze[i] = approach(self._gaze[i], self._gaze_target[i], 6.0, dt)

        # Listening pulls bubbles in; speaking blows them out.
        self._emit_in += dt * w[Mode.LISTENING] * (1.5 + 14.0 * level)
        while self._emit_in >= 1.0:
            self._emit_in -= 1.0
            self._spawn_inward()
        self._emit_out += dt * w[Mode.SPEAKING] * (1.0 + 16.0 * level)
        while self._emit_out >= 1.0:
            self._emit_out -= 1.0
            self._spawn_outward()

        # A ripple ring on every syllable peak while speaking.
        self._ring_cooldown -= dt
        if mode is Mode.SPEAKING and level > 0.45 >= self._last_level and self._ring_cooldown <= 0:
            self.rings.append(Ring())
            self._ring_cooldown = 0.25
        self._last_level = level

        for b in self.bubbles:
            b.age += dt
            if b.inward:
                b.x += b.vx * dt
                b.y += b.vy * dt
                if math.hypot(b.x, b.y) < 1.04:
                    b.dead = True
            else:
                b.vy -= 0.25 * dt
                b.vx += math.sin(t * 4 + b.seed) * 0.3 * dt
                b.x += b.vx * dt
                b.y += b.vy * dt
                if b.age >= b.life:
                    b.dead = True
        self.bubbles = [b for b in self.bubbles if not b.dead]

        for ring in self.rings:
            ring.age += dt
        self.rings = [r for r in self.rings if r.age < r.life]

    def _spawn_inward(self) -> None:
        rng = self._rng
        a = rng.uniform(0, TAU)
        dist = rng.uniform(1.9, 2.6)
        speed = rng.uniform(0.5, 0.95)
        swirl = rng.uniform(-0.25, 0.25)
        x, y = math.cos(a) * dist, math.sin(a) * dist
        vx = -math.cos(a) * speed - math.sin(a) * swirl
        vy = -math.sin(a) * speed + math.cos(a) * swirl
        self.bubbles.append(Bubble(x, y, vx, vy, rng.uniform(0.03, 0.08), True, 10.0))

    def _spawn_outward(self) -> None:
        rng = self._rng
        a = -math.pi / 2 + rng.gauss(0, 0.9)
        speed = rng.uniform(0.35, 0.8)
        self.bubbles.append(Bubble(
            math.cos(a) * 1.0, math.sin(a) * 1.0,
            math.cos(a) * speed, math.sin(a) * speed - 0.25,
            rng.uniform(0.03, 0.11), False, rng.uniform(1.8, 3.0)))

    # ------------------------------------------------------------------- paint

    def paint(self, p: QPainter, cx: float, cy: float, R: float) -> None:
        w = self.weights
        listen, speak, think, idle = w[Mode.LISTENING], w[Mode.SPEAKING], w[Mode.THINKING], w[Mode.IDLE]
        level, t = self.level, self.t
        voice = listen + speak

        bob = math.sin(t * 1.3) * R * 0.045 * (idle + think) - level * speak * R * 0.05
        by = cy + bob
        scale = 1.0 + 0.025 * math.sin(t * 1.6) + 0.10 * level * voice
        rx = R * scale * (1.0 + 0.035 * level * speak)
        ry = R * scale * (0.97 - 0.035 * level * speak)
        wobble = 0.018 + listen * (0.02 + 0.07 * level) + speak * (0.015 + 0.08 * level) + think * 0.02

        p.setPen(Qt.PenStyle.NoPen)
        self._paint_glow(p, cx, by, R, listen, voice, think)
        self._paint_halos(p, cx, by, R, listen, wobble)
        self._paint_rings(p, cx, by, R)
        self._paint_shadow(p, cx, cy, R, bob)

        body = blob_path(cx, by, rx, ry, t, wobble, self._spin)
        self._paint_body(p, body, cx, by, R)
        self._paint_face(p, cx, by, R * scale, listen, speak, think, idle)
        self._paint_thinking_dots(p, cx, by, R, think)
        self._paint_bubbles(p, cx, by, R)

    def _paint_glow(self, p, cx, cy, R, listen, voice, think) -> None:
        level = self.level
        radius = R * (2.1 + 0.8 * level * voice)
        alpha = 38 + 110 * level * voice + 25 * think
        g = QRadialGradient(QPointF(cx, cy), radius)
        g.setColorAt(0.0, rgba(CORAL, alpha))
        g.setColorAt(0.5, rgba(CORAL, alpha * 0.3))
        g.setColorAt(1.0, rgba(CORAL, 0))
        p.setBrush(g)
        p.drawEllipse(QPointF(cx, cy), radius, radius)
        if listen > 0.01:
            radius = R * (2.4 + 0.6 * level)
            g = QRadialGradient(QPointF(cx, cy), radius)
            g.setColorAt(0.35, rgba(LISTEN_BLUE, 60 * listen * (0.4 + level)))
            g.setColorAt(1.0, rgba(LISTEN_BLUE, 0))
            p.setBrush(g)
            p.drawEllipse(QPointF(cx, cy), radius, radius)

    def _paint_halos(self, p, cx, cy, R, listen, wobble) -> None:
        if listen < 0.01:
            return
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i, base in enumerate((1.22, 1.42, 1.64)):
            s = base + 0.2 * self.level * (1 - i * 0.2) + 0.02 * math.sin(self.t * 2 + i)
            path = blob_path(cx, cy, R * s, R * s, self.t + i * 0.7, wobble * 1.3, -self._spin)
            p.setPen(QPen(rgba(LISTEN_BLUE, listen * (75 - i * 20) * (0.5 + self.level)), 1.6))
            p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)

    def _paint_rings(self, p, cx, cy, R) -> None:
        p.setBrush(Qt.BrushStyle.NoBrush)
        for ring in self.rings:
            k = ring.age / ring.life
            radius = R * (1.05 + 1.3 * k)
            p.setPen(QPen(rgba((255, 160, 130), 120 * (1 - k) ** 2), 0.6 + 2.2 * (1 - k)))
            p.drawEllipse(QPointF(cx, cy), radius, radius)
        p.setPen(Qt.PenStyle.NoPen)

    def _paint_shadow(self, p, cx, cy, R, bob) -> None:
        lift = max(0.6, 1.0 - bob / R)
        sx, sy = R * 1.0 * lift, R * 0.13 * lift
        g = QRadialGradient(QPointF(cx, cy + R * 1.38), sx)
        g.setColorAt(0.0, QColor(0, 0, 0, 120))
        g.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.save()
        p.translate(cx, cy + R * 1.38)
        p.scale(1.0, sy / sx)
        p.translate(-cx, -(cy + R * 1.38))
        p.setBrush(g)
        p.drawEllipse(QPointF(cx, cy + R * 1.38), sx, sx)
        p.restore()

    def _paint_body(self, p, body, cx, cy, R) -> None:
        lift = 18 * self.level
        g = QRadialGradient(QPointF(cx - R * 0.32, cy - R * 0.38), R * 1.55)
        g.setColorAt(0.0, rgba(tuple(min(255, c + int(lift)) for c in CORAL_LIGHT), 255))
        g.setColorAt(0.45, rgba(tuple(min(255, c + int(lift)) for c in CORAL), 255))
        g.setColorAt(1.0, rgba(CORAL_DEEP, 255))
        p.setBrush(g)
        p.drawPath(body)

        # Soft specular highlight, clipped to the body.
        p.save()
        p.setClipPath(body)
        hx, hy = cx - R * 0.38, cy - R * 0.5
        hg = QRadialGradient(QPointF(hx, hy), R * 0.45)
        hg.setColorAt(0.0, QColor(255, 255, 255, 110))
        hg.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(hg)
        p.drawEllipse(QPointF(hx, hy), R * 0.45, R * 0.45)
        p.restore()

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 214, 196, 55), 1.5))
        p.drawPath(body)
        p.setPen(Qt.PenStyle.NoPen)

    def _paint_face(self, p, cx, cy, R, listen, speak, think, idle) -> None:
        gx, gy = self._gaze
        level = self.level
        fx, fy = cx + gx * R * 0.05, cy + gy * R * 0.04

        # Eyes.
        openness = 1.0
        if self._blink_t >= 0:
            openness = 1.0 - math.sin(math.pi * self._blink_t / BLINK_SECONDS) * 0.92
        eye_w = R * 0.135 * (1 + 0.08 * listen)
        eye_h = R * 0.215 * (1 + 0.12 * listen) * openness * (1 - 0.15 * speak * level)
        for side in (-1, 1):
            ex = fx + side * R * 0.33 + gx * R * 0.07
            ey = fy - R * 0.1 + gy * R * 0.06
            p.setBrush(rgba(INK, 255))
            p.drawEllipse(QPointF(ex, ey), eye_w / 2, eye_h / 2)
            if openness > 0.5:
                p.setBrush(QColor(255, 255, 255, 230))
                p.drawEllipse(QPointF(ex - eye_w * 0.16, ey - eye_h * 0.2), eye_w * 0.19, eye_w * 0.19)

        # Cheeks.
        p.setBrush(QColor(255, 118, 110, int(50 + 60 * speak * level + 20 * listen)))
        for side in (-1, 1):
            p.drawEllipse(QPointF(fx + side * R * 0.56, fy + R * 0.13), R * 0.12, R * 0.07)

        # Mouth: a smile that opens into a talking mouth with the voice level.
        mx = fx + gx * R * 0.04 + think * R * 0.07
        my = fy + R * 0.2
        talk = speak * level
        smile_alpha = 255 * max(0.0, 1.0 - talk * 7)
        if smile_alpha > 1:
            curve = idle * 1.0 + listen * 0.65 + think * 0.1 + speak * 0.9
            half = R * 0.13 * (1 - 0.35 * think)
            smile = QPainterPath()
            smile.moveTo(mx - half, my)
            smile.quadTo(mx, my + R * 0.12 * curve, mx + half, my - R * 0.02 * think)
            pen = QPen(rgba(INK, smile_alpha), R * 0.045)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(smile)
            p.setPen(Qt.PenStyle.NoPen)
        if talk > 0.03:
            mw = R * (0.11 - 0.02 * talk)
            mh = R * (0.025 + 0.13 * talk)
            mouth = QPainterPath()
            mouth.addEllipse(QPointF(mx, my + mh * 0.3), mw, mh)
            p.setBrush(rgba(INK, 255 * min(1.0, talk * 7)))
            p.drawPath(mouth)
            p.save()
            p.setClipPath(mouth)
            p.setBrush(QColor(236, 112, 96, int(255 * min(1.0, talk * 7))))
            p.drawEllipse(QPointF(mx, my + mh * 1.1), mw * 0.8, mh * 0.7)
            p.restore()

    def _paint_thinking_dots(self, p, cx, cy, R, think) -> None:
        if think < 0.01:
            return
        for i, size in enumerate((0.075, 0.058, 0.042)):
            a = self._spin * 1.6 - i * 0.45
            x, y = cx + math.cos(a) * R * 1.5, cy + math.sin(a) * R * 1.5
            p.setBrush(QColor(255, 206, 186, int(think * (230 - i * 60))))
            p.drawEllipse(QPointF(x, y), R * size, R * size)

    def _paint_bubbles(self, p, cx, cy, R) -> None:
        for b in self.bubbles:
            a = b.alpha()
            if a <= 0.01:
                continue
            x, y, r = cx + b.x * R, cy + b.y * R, b.r * R
            tint = LISTEN_BLUE if b.inward else SPEAK_WARM
            g = QRadialGradient(QPointF(x - r * 0.3, y - r * 0.3), r * 1.3)
            g.setColorAt(0.0, QColor(255, 255, 255, int(70 * a)))
            g.setColorAt(0.7, rgba(tint, 25 * a))
            g.setColorAt(1.0, rgba(tint, 70 * a))
            p.setBrush(g)
            p.setPen(QPen(rgba(tint, 180 * a), max(1.0, r * 0.12)))
            p.drawEllipse(QPointF(x, y), r, r)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, int(210 * a)))
            p.drawEllipse(QPointF(x - r * 0.35, y - r * 0.4), r * 0.22, r * 0.22)
