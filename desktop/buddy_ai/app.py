"""Application entry point."""

from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPixmap, QRadialGradient
from PySide6.QtWidgets import QApplication

from .window import MainWindow


def _app_icon() -> QIcon:
    pix = QPixmap(128, 128)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QRadialGradient(QPointF(48, 44), 90)
    g.setColorAt(0.0, QColor(255, 196, 170))
    g.setColorAt(0.5, QColor(232, 128, 94))
    g.setColorAt(1.0, QColor(176, 76, 50))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(g)
    p.drawEllipse(QPointF(64, 64), 58, 56)
    p.setBrush(QColor(66, 26, 18))
    p.drawEllipse(QPointF(45, 58), 7, 11)
    p.drawEllipse(QPointF(83, 58), 7, 11)
    p.end()
    return QIcon(pix)


def _use_dark_title_bar(window) -> None:
    """Ask Windows 10/11 for a dark caption so the frame matches the app."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = int(window.winId())
        dwm = ctypes.windll.dwmapi
        on = ctypes.c_int(1)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new, old)
            if dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(on), ctypes.sizeof(on)) == 0:
                break
        caption = ctypes.c_int(0x00161616)  # DWMWA_CAPTION_COLOR, Windows 11 only
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
    except (AttributeError, OSError):
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Buddy AI voice interface (simulated audio).")
    parser.add_argument("--name", default="Favour", help="name used in the greeting")
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Buddy AI")
    app.setWindowIcon(_app_icon())

    window = MainWindow(args.name)
    screen = QGuiApplication.primaryScreen().availableGeometry()
    window.resize(min(430, screen.width()), min(880, int(screen.height() * 0.92)))
    window.show()
    _use_dark_title_bar(window)
    return app.exec()
