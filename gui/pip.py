"""gui/pip.py — Picture-in-Picture (PiP) Floating Mini Core for JARVIS.

A compact, floating, frameless, always-on-top holographic widget.
Displays the glowing animated Neural Reactor Core avatar, state pill, and live audio levels.
Allows dragging anywhere on screen, talking to JARVIS while working in other apps,
and double-clicking or pressing EXPAND to seamlessly return to the full application window.
"""

from __future__ import annotations

import math
import time
from PyQt6.QtCore import Qt, QPoint, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QRadialGradient,
    QLinearGradient, QMouseEvent
)
from PyQt6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QLabel

from gui.theme import C
from gui.style import px_font, hud_font


class PipWindow(QWidget):
    """Floating Always-on-Top Mini Core HUD."""

    restore_requested = pyqtSignal()
    mute_toggled      = pyqtSignal()

    _SIZE = 260

    def __init__(self, parent=None):
        super().__init__(None)  # Top-level window so it stays on top independently
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setMouseTracking(True)

        self.state        = "LISTENING"
        self.muted        = False
        self.audio_level  = 0.0
        self._core_phase  = 0.0
        self._viseme_open = 0.0
        self._drag_pos    = QPoint()
        self._hovered     = False

        # 60 FPS Core Animation Timer
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self._init_controls()

    def _init_controls(self):
        # Hover Control Buttons (Expand / Restore, Mute, Close)
        self._ctrl_widget = QWidget(self)
        self._ctrl_widget.setGeometry(15, self._SIZE - 46, self._SIZE - 30, 36)
        self._ctrl_widget.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self._ctrl_widget)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(6)

        btn_style = f"""
            QPushButton {{
                background: rgba(18, 20, 26, 220);
                color: {C.PRI};
                border: 1px solid {C.BORDER_A};
                border-radius: 4px;
                padding: 4px 8px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO};
                color: {C.WHITE};
                border-color: {C.PRI};
            }}
        """

        self._restore_btn = QPushButton("EXPAND ⤢", self._ctrl_widget)
        self._restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._restore_btn.setStyleSheet(btn_style)
        self._restore_btn.setToolTip("Restore Full Application Window  [F9]")
        self._restore_btn.clicked.connect(self.restore_requested.emit)
        lay.addWidget(self._restore_btn)

        self._mute_btn = QPushButton("MIC", self._ctrl_widget)
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.setStyleSheet(btn_style)
        self._mute_btn.setToolTip("Toggle Mute  [F4]")
        self._mute_btn.clicked.connect(self.mute_toggled.emit)
        lay.addWidget(self._mute_btn)

        self._ctrl_widget.hide()

    def _tick(self):
        self._core_phase += 0.03
        self.update()

    def set_state(self, state: str):
        self.state = (state or "LISTENING").upper()
        self.update()

    def set_audio_level(self, level: float):
        self.audio_level = max(0.0, min(1.0, float(level)))

    def set_viseme(self, openness: float):
        self._viseme_open = max(0.0, min(1.0, float(openness)))

    def set_muted(self, muted: bool):
        self.muted = bool(muted)
        if hasattr(self, "_mute_btn"):
            self._mute_btn.setText("MUTED" if self.muted else "MIC")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {'rgba(120, 20, 20, 220)' if self.muted else 'rgba(18, 20, 26, 220)'};
                    color: {'#ff5555' if self.muted else C.PRI};
                    border: 1px solid {C.BORDER_A};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }}
            """)
        self.update()

    # ── Mouse & Drag Handling ───────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.restore_requested.emit()
            event.accept()

    def enterEvent(self, event):
        self._hovered = True
        self._ctrl_widget.show()
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self._ctrl_widget.hide()
        self.update()

    # ── Painting the Neural Reactor Core Avatar ─────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W = float(self.width())
        H = float(self.height())
        cx = W / 2.0
        cy = H / 2.0
        r_outer = min(cx, cy) - 6.0

        # 1. Dark glowing sci-fi circular container
        bg_grad = QRadialGradient(cx, cy, r_outer)
        bg_grad.setColorAt(0.0, QColor(14, 18, 26, 245))
        bg_grad.setColorAt(0.85, QColor(8, 10, 15, 250))
        bg_grad.setColorAt(1.0, QColor(5, 6, 10, 255))
        p.setBrush(QBrush(bg_grad))
        p.setPen(QPen(QColor(C.PRI), 1.5))
        p.drawEllipse(QRectF(cx - r_outer, cy - r_outer, r_outer * 2.0, r_outer * 2.0))

        # 2. Outer decorative tech tick marks
        p.setPen(QPen(QColor(C.BORDER_A), 1.0))
        num_ticks = 36
        for i in range(num_ticks):
            angle = (i * (360.0 / num_ticks)) * (math.pi / 180.0)
            inner_r = r_outer - 5.0
            outer_r = r_outer - 1.5
            x1 = cx + math.cos(angle) * inner_r
            y1 = cy + math.sin(angle) * inner_r
            x2 = cx + math.cos(angle) * outer_r
            y2 = cy + math.sin(angle) * outer_r
            p.drawLine(QPoint(int(x1), int(y1)), QPoint(int(x2), int(y2)))

        # 3. Rotating reactor concentric rings
        phase = self._core_phase
        audio_boost = self.audio_level * 18.0 + self._viseme_open * 12.0

        # Ring 1 (Inner counter-rotating)
        r1 = 38.0 + audio_boost * 0.4
        p.setPen(QPen(QColor(C.PRI), 1.2, Qt.PenStyle.DashLine))
        p.save()
        p.translate(cx, cy)
        p.rotate(-phase * 35.0)
        p.drawEllipse(QRectF(-r1, -r1, r1 * 2.0, r1 * 2.0))
        p.restore()

        # Ring 2 (Middle segmented rotating)
        r2 = 56.0 + audio_boost * 0.7
        p.setPen(QPen(QColor(C.PRI_LIGHT), 1.6))
        p.save()
        p.translate(cx, cy)
        p.rotate(phase * 45.0)
        for a in range(0, 360, 45):
            p.drawArc(QRectF(-r2, -r2, r2 * 2.0, r2 * 2.0), a * 16, 25 * 16)
        p.restore()

        # Ring 3 (Outer glowing audio-reactive orbit)
        r3 = 78.0 + audio_boost
        p.setPen(QPen(QColor(C.PRI), 1.0, Qt.PenStyle.DotLine))
        p.drawEllipse(QRectF(cx - r3, cy - r3, r3 * 2.0, r3 * 2.0))

        # 4. Central Glowing Arc Chamber
        core_r = 24.0 + audio_boost * 0.8
        core_grad = QRadialGradient(cx, cy, core_r)
        if self.muted:
            core_grad.setColorAt(0.0, QColor(255, 80, 80, 240))
            core_grad.setColorAt(0.6, QColor(180, 40, 40, 160))
            core_grad.setColorAt(1.0, QColor(80, 20, 20, 0))
        elif self.state == "SPEAKING":
            core_grad.setColorAt(0.0, QColor(100, 240, 255, 255))
            core_grad.setColorAt(0.5, QColor(0, 180, 230, 200))
            core_grad.setColorAt(1.0, QColor(0, 100, 180, 0))
        elif self.state == "THINKING":
            core_grad.setColorAt(0.0, QColor(255, 200, 60, 255))
            core_grad.setColorAt(0.5, QColor(220, 140, 20, 180))
            core_grad.setColorAt(1.0, QColor(140, 80, 0, 0))
        else:  # LISTENING
            core_grad.setColorAt(0.0, QColor(120, 255, 160, 255))
            core_grad.setColorAt(0.5, QColor(40, 200, 100, 180))
            core_grad.setColorAt(1.0, QColor(20, 120, 50, 0))

        p.setBrush(QBrush(core_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2.0, core_r * 2.0))

        # Triangle Core Glyph
        p.save()
        p.translate(cx, cy)
        p.rotate(phase * 20.0)
        p.setPen(QPen(QColor(C.WHITE), 1.5))
        tri_r = 14.0 + audio_boost * 0.3
        p.drawLine(QPoint(0, int(-tri_r)), QPoint(int(tri_r * 0.866), int(tri_r * 0.5)))
        p.drawLine(QPoint(int(tri_r * 0.866), int(tri_r * 0.5)), QPoint(int(-tri_r * 0.866), int(tri_r * 0.5)))
        p.drawLine(QPoint(int(-tri_r * 0.866), int(tri_r * 0.5)), QPoint(0, int(-tri_r)))
        p.restore()

        # 5. Top Status Badge Pill
        p.setFont(hud_font(7, QFont.Weight.Bold))
        status_txt = "MUTED" if self.muted else self.state
        status_w = 90.0
        status_h = 18.0
        status_rect = QRectF(cx - status_w / 2.0, cy - r_outer + 12.0, status_w, status_h)

        status_col = (
            QColor("#ff4444") if self.muted
            else QColor("#00d4ff") if self.state == "SPEAKING"
            else QColor("#ffaa00") if self.state == "THINKING"
            else QColor("#00ff88")
        )

        p.setBrush(QBrush(QColor(10, 14, 20, 200)))
        p.setPen(QPen(status_col, 1.0))
        p.drawRoundedRect(status_rect, 9.0, 9.0)

        p.setPen(status_col)
        p.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, f"● {status_txt}")
