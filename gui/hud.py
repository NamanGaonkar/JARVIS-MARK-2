"""gui/hud.py — The centre of the HUD: the avatar or the reactor core, the state line and the waveform.

Split out of ui.py in Mark LVII; behaviour unchanged."""
from __future__ import annotations

import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

from PyQt6.QtCore import (
    QEasingCurve, QLineF, QMimeData, QObject, QParallelAnimationGroup, QPointF,
    QPoint, QPropertyAnimation, QRect, QRectF, QSize, QSizeF, Qt, QTimer,
    QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QDragEnterEvent, QDropEvent, QFont,
    QFontDatabase, QKeySequence, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QGraphicsScene, QGraphicsView, QGraphicsPixmapItem,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget, QProgressBar, QSlider,
)

from gui.theme import (
    C,
    HoloAvatar,
    qcol,
)

from gui.style import blend, chamfer, px_font, with_alpha

try:
    from gui.reactor import Reactor3D
except Exception:      # pragma: no cover — the classic core still draws
    Reactor3D = None


class HudCanvas(QWidget):
    def __init__(self, face_path: str, assistant_name: str = "J.A.R.V.I.S", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"
        self._assistant_name = assistant_name

        # The holographic head that fills the HUD. If it could not be imported
        # we fall back to the old glowing core so the panel is never empty.
        self._avatar = None
        if HoloAvatar is not None:
            try:
                self._avatar = HoloAvatar()
            except Exception:
                self._avatar = None

        # The reactor core in three dimensions (gui/reactor.py). The flat ring
        # stack it replaced is kept whole as _paint_core_classic, and it is
        # what draws if the model could not be built.
        self._reactor = None
        if Reactor3D is not None:
            try:
                self._reactor = Reactor3D()
            except Exception:
                self._reactor = None

        # Which centrepiece to draw. Read once here and changed live by the
        # settings toggle; the avatar object is kept either way so switching
        # back is instant and costs no reload.
        try:
            from memory.config_manager import get_hud_style
            self.hud_style = get_hud_style()
        except Exception:
            self.hud_style = "core"
        self._core_phase = 0.0

        # Live HUD logs displayed on the left side, matching movie JARVIS HUD
        self._hud_logs: list[tuple[str, str, str]] = [
            (time.strftime("%H:%M:%S"), "SYSTEM", "JARVIS CORE ONLINE"),
            (time.strftime("%H:%M:%S"), "LINK", "BACKEND ONLINE"),
        ]

        # Live location and clickable interactive real map
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._map_rect = QRectF()
        self._exit_btn_rect = QRectF()
        self._hover_exit = False
        self.on_exit_hud = None
        self._map_pixmap: QPixmap | None = None
        try:
            from pathlib import Path
            map_path = Path("config/tactical_map.png")
            if map_path.exists():
                self._map_pixmap = QPixmap(str(map_path))
        except Exception:
            self._map_pixmap = None

        try:
            from core.location import get_location
            self._loc_info = get_location()
        except Exception:
            self._loc_info = {"city": "Panjim", "region": "Goa", "label": "PANJIM, GOA", "coords_str": "15.5016° N, 73.8234° E"}

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 55.0
        self._tgt_halo   = 55.0
        self._last_t     = time.time()
        self._step_t     = time.time()
        self._blink      = True
        self._blink_tick = 0

        # Rescaled-face cache: the smooth rescale is expensive, so we keep the
        # last result and only rebuild it when the (quantised) size changes.

        # Static grid-dot layer, pre-rendered once per size/theme into a pixmap
        # so paintEvent blits it in one call instead of thousands of drawPoint()s.
        self._grid_cache: QPixmap | None = None
        self._grid_key = None
        # Repaint throttle counter (idle frames drop to ~20 Hz — see _step()).
        self._paint_tick = 0

        # Live audio reactivity: _live_amp is written from the audio threads
        # (0.0–1.0), _amp_disp is the smoothed value the paint code reads.
        self._live_amp  = 0.0
        self._amp_disp  = 0.0
        # (frames, start_time, hop) posted by the playback thread — see
        # push_visemes(). None means "no schedule; use the plain level".
        self._visemes = None
        self._vis_i = None        # first schedule frame not yet handed to the mouth
        self._base_scale = 1.0    # slow "breathing" target; amp is added per-frame
        self._base_halo  = 55.0

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def glance(self, dx: float, dy: float, hold: float = 1.1) -> None:
        """Ask the avatar to look somewhere for a moment (see HoloAvatar.glance)."""
        try:
            if self._avatar is not None:
                self._avatar.glance(dx, dy, hold)
        except Exception:
            pass

    def push_visemes(self, frames, hop: float, at: float) -> None:
        """Thread-safe: hand over a schedule of (level, openness, width) frames.

        The playback thread writes up to 200 ms of audio in one go, so a single
        averaged level would only move the mouth five times a second — enough to
        flap, nowhere near enough to articulate. It instead posts the whole
        slice's worth of 20 ms frames here and `_step()` plays them out against
        the wall clock, in step with the audio going to the speakers.

        `at` is the wall-clock time this batch will *begin to sound*, which the
        caller tracks as a playback cursor. It is not the time of the call, and
        the difference is the whole point: `stream.write` returns once the buffer
        accepts the samples, so consecutive batches are handed over far faster
        than they play. Anchoring each one to "now" made every batch start while
        its predecessor was still sounding, so each schedule replaced the last
        after a couple of frames and the mouth only ever played the opening
        instant of every 200 ms — the reason it did not match the words.

        Successive batches are therefore *appended* into one continuous
        timeline, not swapped in. A paragraph is one schedule; the mouth stops
        falling into a gap at every chunk boundary and having to climb back out.
        """
        try:
            if not frames:
                return
            hop = max(1e-3, float(hop))
            at = float(at)
            new = list(frames)
            cur = self._visemes
            if cur is not None:
                old, t0, ohop = cur
                if abs(ohop - hop) < 1e-6:
                    # Where in the existing timeline does this batch land?
                    i = int(round((at - t0) / hop))
                    if 0 <= i <= len(old) + 1:
                        # Continues (or slightly overlaps) what is already
                        # queued: extend rather than restart. Drop whatever has
                        # already been played so the list cannot grow without
                        # bound over a long reply.
                        merged = old[:i] + new
                        played = int((time.time() - t0) / hop) - 2
                        if played > 60:
                            merged = merged[played:]
                            t0 += played * hop
                            if self._vis_i is not None:
                                self._vis_i = max(0, self._vis_i - played)
                        self._visemes = (merged, t0, hop)
                        return
            self._visemes = (new, at, hop)
            self._vis_i = None
        except Exception:
            pass

    def set_audio_level(self, level: float) -> None:
        """Thread-safe entry point for the audio threads. Stores the louder of
        the incoming level and the current value so brief gaps between chunks
        don't make the waveform stutter; _step() decays it back down."""
        try:
            lv = float(level)
        except (TypeError, ValueError):
            return
        if lv < 0.0:
            lv = 0.0
        elif lv > 1.0:
            lv = 1.0
        if lv > self._live_amp:
            self._live_amp = lv

    def append_hud_log(self, text: str) -> None:
        """Push a log entry to be displayed directly on the HUD screen in amber monospace."""
        try:
            ts = time.strftime("%H:%M:%S")
            head, sep, rest = text.partition(":")
            if sep and len(head.strip()) <= 10:
                tag = head.strip().upper()
                msg = rest.strip()
            else:
                tag = "SYSTEM"
                msg = text.strip()
            self._hud_logs.append((ts, tag, msg))
            if len(self._hud_logs) > 7:
                self._hud_logs.pop(0)
            self.update()
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            if hasattr(self, "_exit_btn_rect") and self._exit_btn_rect.contains(pos):
                if hasattr(self, "on_exit_hud") and callable(self.on_exit_hud):
                    self.on_exit_hud()
                return
            if hasattr(self, "_map_rect") and self._map_rect.contains(pos):
                try:
                    from core.location import open_live_map
                    open_live_map()
                    self.append_hud_log("MAP: Satellite navigation coordinates opened.")
                except Exception as e:
                    print(f"[HUD] map click: {e}")
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        hover_exit = hasattr(self, "_exit_btn_rect") and self._exit_btn_rect.contains(pos)
        hover_map = hasattr(self, "_map_rect") and self._map_rect.contains(pos)
        if getattr(self, "_hover_exit", False) != hover_exit:
            self._hover_exit = hover_exit
            self.update()
        if hover_exit or hover_map:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Escape, Qt.Key.Key_F10):
            if hasattr(self, "on_exit_hud") and callable(self.on_exit_hud):
                self.on_exit_hud()
                return
        super().keyPressEvent(event)

    def _make_grid(self, W: int, H: int) -> QPixmap:
        """Pre-render the static backdrop — pure cinematic black void with soft amber core radiance."""
        W, H = max(1, W), max(1, H)
        pm = QPixmap(W, H)
        pm.fill(qcol(C.BG))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = W / 2, H / 2

        # Subtle warm amber core ambient glow in center
        g = QRadialGradient(cx, cy, max(W, H) * 0.55)
        g.setColorAt(0.0, with_alpha(C.PRI, 0.07))
        g.setColorAt(0.35, with_alpha(C.PRI, 0.025))
        g.setColorAt(0.70, with_alpha(C.BG, 0.0))
        g.setColorAt(1.0, qcol(C.BG))
        p.fillRect(QRectF(0, 0, W, H), QBrush(g))

        # Thin cinematic edge frame marks
        m, cut, arm = 6, 16, 42
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(blend(C.PRI, 0.35), 1.2))
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            x0 = m if sx > 0 else W - m
            y0 = m if sy > 0 else H - m
            p.drawLine(QLineF(x0, y0 + sy * (cut + arm), x0, y0 + sy * cut))
            p.drawLine(QLineF(x0, y0 + sy * cut, x0 + sx * cut, y0))

        p.end()
        return pm

    def _step(self):
        self._tick += 1
        now = time.time()

        # ── Live audio reactivity ────────────────────────────────────────────
        # A viseme schedule, if one is playing, gives both the level and the
        # mouth shape for this exact instant; otherwise fall back to the peak
        # level the audio threads pushed in.
        v_open = v_wide = v_level = None
        v_seq = None
        sched = self._visemes
        if sched is not None:
            frames, t0, hop = sched
            i = int((now - t0) / hop)
            if 0 <= i < len(frames):
                # Hand over *every* frame since the last tick, not just the one
                # under the cursor. This timer runs at 60 Hz but the paint is
                # throttled and the machine may be busy, so a tick can span two
                # or three 20 ms frames — and a consonant closure is only two
                # frames long. Sampling one and discarding the rest is how the
                # closures between words went missing.
                j = self._vis_i if self._vis_i is not None else i
                v_seq = frames[max(0, j):i + 1]
                self._vis_i = max(j, i + 1)
                v_level, v_open, v_wide = frames[i]
                if v_seq:
                    peak = max(f[0] for f in v_seq)
                    if peak > self._live_amp:
                        self._live_amp = peak
            elif i >= len(frames):
                self._visemes = None        # schedule spent
                self._vis_i = None

        # Audio threads push peaks into _live_amp; decay it toward silence so
        # gaps between chunks fade out instead of freezing, then smooth it.
        self._live_amp *= 0.86
        self._amp_disp += (self._live_amp - self._amp_disp) * 0.45
        amp = self._amp_disp

        # The avatar animates off the very same smoothed level the waveform
        # uses — one audio source, so the mouth can never drift out of sync.
        dt = now - self._step_t
        self._step_t = now
        # Integrated, not derived from absolute time: multiplying wall-clock by
        # a rate that changes with state jumps the rings the instant JARVIS
        # starts talking. Same lesson the head's sway taught.
        self._core_phase += min(0.10, max(0.0, dt))

        if self._avatar is not None and self.hud_style == "face":
            self._avatar.step(dt, amp, speaking=self.speaking,
                              muted=self.muted, state=self.state,
                              v_open=v_open, v_wide=v_wide or 0.0,
                              v_level=v_level, v_seq=v_seq,
                              v_hop=(sched[2] if sched is not None else 0.02))
        else:
            if self._reactor is not None:
                self._reactor.step(dt, self.speaking,
                                   self.state in ("THINKING", "PROCESSING"), self.muted)
            # Fallback core: slow "breathing" base target, lifted by the level.
            if now - self._last_t > (0.12 if self.speaking else 0.5):
                if self.speaking:
                    self._base_scale = 1.03
                    self._base_halo  = 122.0
                elif self.muted:
                    self._base_scale = random.uniform(0.998, 1.002)
                    self._base_halo  = random.uniform(15, 28)
                else:
                    self._base_scale = random.uniform(1.001, 1.008)
                    self._base_halo  = random.uniform(48, 68)
                self._last_t = now

            if self.muted:
                self._tgt_scale, self._tgt_halo = self._base_scale, self._base_halo
            elif self.speaking:
                self._tgt_scale = self._base_scale + amp * 0.13
                self._tgt_halo  = self._base_halo  + amp * 95.0
            else:
                self._tgt_scale = self._base_scale + amp * 0.06
                self._tgt_halo  = self._base_halo  + amp * 75.0

            sp = 0.38 if self.speaking else (0.30 if amp > 0.02 else 0.15)
            self._scale += (self._tgt_scale - self._scale) * sp
            self._halo  += (self._tgt_halo  - self._halo)  * sp

        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
            _blinked = True
        else:
            _blinked = False

        # Repaint throttling — advancing the animation state above is cheap at
        # 60 Hz, but the paint is heavy. Active (speaking, audio, thinking) runs
        # at ~30 Hz, which is the frame rate animation has used for talking
        # characters forever and is indistinguishable here; idle drops to ~20 Hz
        # so a sleeping HUD stops pinning a CPU core. The visuals stay smooth
        # either way because the animation state keeps stepping at 60 Hz.
        self._paint_tick = (self._paint_tick + 1) % 6
        active = (self.speaking or amp > 0.02
                  or self.state in ("THINKING", "PROCESSING"))
        if _blinked or (self._paint_tick % 2 == 0 if active
                        else self._paint_tick % 3 == 0):
            # Nothing is on screen when the window is hidden or minimised, so
            # rendering the avatar into it is pure waste — and this app is meant
            # to sit running all day. The animation state above keeps stepping,
            # so it picks up mid-motion instead of snapping when you come back.
            if self._on_screen():
                self.update()

    def _on_screen(self) -> bool:
        """True only when this canvas can actually be seen by the user."""
        try:
            if not self.isVisible():
                return False
            win = self.window()
            return not (win.isMinimized() or win.isHidden())
        except Exception:
            return True      # never let a visibility check stop the HUD drawing

    # ── reactor core ─────────────────────────────────────────────────────────
    # The centrepiece for anyone who did not want a face looking back at them.
    # Built from the same budget as the head — software QPainter, no GPU — and
    # from the same principle: everything on it means something. The rings turn
    # at a rate the state sets, the spectrum ring is the real audio level, and
    # the core brightens with the voice. Nothing here is decoration that moves
    # for its own sake, which is what made the old glowing orb feel dead.

    def _core_colours(self):
        if self.muted:
            return qcol(C.MUTED_C), qcol(C.MUTED_C)
        if self.speaking:
            return qcol(C.PRI), qcol(C.ACC)
        if self.state in ("THINKING", "PROCESSING"):
            return qcol(C.PRI), qcol(C.ACC2)
        if self.state == "LISTENING":
            return qcol(C.PRI), qcol(C.GREEN)
        return qcol(C.PRI), qcol(C.PRI_DIM)

    def _paint_core(self, p: QPainter, cx: float, cy: float, r: float,
                    W: float = 0.0, H: float = 0.0):
        """Draw the reactor core centred on (cx, cy) with core radius r.

        The 3-D model when it was built, the flat ring stack otherwise. Going
        back to the flat one for good is this method calling
        _paint_core_classic, which is kept whole for exactly that."""
        if self._reactor is None:
            return self._paint_core_classic(p, cx, cy, r, W, H)
        main, acc = self._core_colours()
        amp = self._amp_disp
        live = (self.speaking or amp > 0.04) and not self.muted
        self._reactor.paint(p, cx, cy, r, main, acc, qcol(C.WHITE), amp, live,
                            self._assistant_name or "")

    def _paint_core_classic(self, p: QPainter, cx: float, cy: float, r: float,
                            W: float = 0.0, H: float = 0.0):
        """Draw the reactor at (cx, cy) with outer radius r, using the whole
        canvas (W x H) for the marks that frame it."""
        main, acc = self._core_colours()
        bg = qcol(C.BG)
        amp = self._amp_disp
        t = self._core_phase
        live = (self.speaking or amp > 0.04) and not self.muted

        def blend(col: QColor, a: float) -> QColor:
            """Pre-mix onto the background instead of asking Qt to composite.
            The raster engine's opaque path is several times faster than its
            translucent one, and everything here is a line or an arc."""
            k = max(0.0, min(1.0, a))
            return QColor(int(bg.red()   + (col.red()   - bg.red())   * k),
                          int(bg.green() + (col.green() - bg.green()) * k),
                          int(bg.blue()  + (col.blue()  - bg.blue())  * k))

        p.setBrush(Qt.BrushStyle.NoBrush)

        # 1. The atmosphere. One radial gradient doing what a stack of discs did
        #    badly: a wide, soft body of light that gives the thing presence
        #    before any detail is read. This single element decides whether the
        #    HUD looks vast or looks small, so it is drawn first and drawn big.
        # Concentrated rather than spread: a gradient reaching the outer rim
        # washes the whole disc a flat dim blue and reads as fog. Ending it at
        # two thirds leaves it a body of light with somewhere to fall off to,
        # which is what makes it look lit rather than tinted.
        lift = 1.0 + 0.55 * amp + (0.18 if self.speaking else 0.0)
        p.setPen(Qt.PenStyle.NoPen)
        for gr, a0, a1 in ((r * 0.70, 0.30, 0.0), (r * 0.34, 0.34, 0.0)):
            g = QRadialGradient(cx, cy, gr)
            g.setColorAt(0.00, blend(main, min(0.95, a0 * lift)))
            g.setColorAt(0.45, blend(main, min(0.95, a0 * lift * 0.52)))
            g.setColorAt(0.78, blend(main, min(0.95, a0 * lift * 0.18)))
            g.setColorAt(1.00, blend(main, a1))
            p.setBrush(QBrush(g))
            p.drawEllipse(QRectF(cx - gr, cy - gr, gr * 2, gr * 2))
        p.setBrush(Qt.BrushStyle.NoBrush)

        # 2. Frame marks at the corners of the whole canvas, not of the circle.
        #    They are what set the scale: the eye reads the reactor as filling
        #    the room rather than sitting in the middle of it.
        if W > 40 and H > 40:
            m, arm = min(W, H) * 0.035, min(W, H) * 0.055
            p.setPen(QPen(blend(main, 0.45), 1.4))
            for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                x = cx + sx * (W / 2 - m)
                y = cy + sy * (H / 2 - m)
                p.drawLine(QLineF(x, y, x - sx * arm, y))
                p.drawLine(QLineF(x, y, x, y - sy * arm))

        # 3. Crosshair across the full canvas, broken around the core so it
        #    frames the reactor rather than crossing it.
        p.setPen(QPen(blend(main, 0.16), 1))
        gap = r * 0.62
        if W > 40:
            p.drawLine(QLineF(cx - W / 2, cy, cx - gap, cy))
            p.drawLine(QLineF(cx + gap, cy, cx + W / 2, cy))
        if H > 40:
            p.drawLine(QLineF(cx, cy - H / 2, cx, cy - gap))
            p.drawLine(QLineF(cx, cy + gap, cx, cy + H / 2))

        # 4. Two thin outer circles. Sparse on purpose — a dense ring reads as a
        #    grey band at this size, and restraint is what made the original
        #    look expensive.
        for rr, a in ((1.00, 0.34), (0.93, 0.16)):
            rad = r * rr
            p.setPen(QPen(blend(main, a), 1))
            p.drawEllipse(QRectF(cx - rad, cy - rad, rad * 2, rad * 2))

        # 5. Long, sparse graduations: 24 majors reaching well in from the rim,
        #    with shorter minors between them.
        major, minor = [], []
        for i in range(72):
            a = math.radians(i * 5.0)
            ca, sa = math.cos(a), math.sin(a)
            if i % 3 == 0:
                major.append(QLineF(cx + ca * r * 0.885, cy + sa * r * 0.885,
                                    cx + ca * r * 0.985, cy + sa * r * 0.985))
            else:
                minor.append(QLineF(cx + ca * r * 0.945, cy + sa * r * 0.945,
                                    cx + ca * r * 0.985, cy + sa * r * 0.985))
        p.setPen(QPen(blend(main, 0.42), 1.3))
        p.drawLines(major)
        p.setPen(QPen(blend(main, 0.18), 1))
        p.drawLines(minor)

        # 6. Sweeping arcs. Long spans, not dashes — the original's grandeur
        #    came from a few big strokes. Speed is the state: idle drifts,
        #    thinking hurries, speaking runs.
        rate = 1.0 + (1.9 if self.state in ("THINKING", "PROCESSING") else 0.0) \
                   + (1.2 if self.speaking else 0.0)
        for k, (rr, span, count, dirn, col, a, wid) in enumerate((
                (0.955, 118, 2, +1, acc,  0.75, 2.0),
                (0.845, 82,  3, -1, main, 0.38, 1.3),
                (0.760, 150, 1, +1, acc,  0.45, 1.6),
                (0.660, 64,  4, -1, main, 0.26, 1.1),
                (0.545, 128, 2, +1, main, 0.30, 1.2))):
            rad = r * rr
            p.setPen(QPen(blend(col, a), wid))
            box = QRectF(cx - rad, cy - rad, rad * 2, rad * 2)
            base = (t * rate * (9 + k * 6) * dirn) % 360.0
            for sgm in range(count):
                p.drawArc(box, int((base + sgm * (360.0 / count)) * 16),
                          int(span * 16))

        # 7. The voice, as a ring of graduations that grow with it. Kept out at
        #    a wide radius so it never crowds the middle.
        n = 60
        ring = r * 0.415
        spikes = []
        for i in range(n):
            a = math.radians(i * (360.0 / n))
            ca, sa = math.cos(a), math.sin(a)
            wob = 0.5 + 0.5 * math.sin(t * 2.3 + i * 0.42)
            idle = 0.018 + 0.012 * math.sin(t * 1.2 + i * 0.7)
            h = r * (idle + (amp * 0.20 * wob if live else 0.0))
            spikes.append(QLineF(cx + ca * ring, cy + sa * ring,
                                 cx + ca * (ring + h), cy + sa * (ring + h)))
        p.setPen(QPen(blend(acc if live else main, 0.25 + 0.5 * amp), 1.6))
        p.drawLines(spikes)

        # 8. The inner ring the name sits in.
        inner = r * 0.355
        p.setPen(QPen(blend(acc, 0.30 + 0.45 * amp), 1.5))
        p.drawEllipse(QRectF(cx - inner, cy - inner, inner * 2, inner * 2))

        # 9. The name, sized from the string rather than from the radius alone:
        #    "J.A.R.V.I.S" and a name someone renamed to "MAX" are very
        #    different widths, and a fixed fraction of r spills one of them past
        #    the ring it is supposed to sit inside.
        name = self._assistant_name or ""
        if name:
            space = max(1.0, r * 0.018)
            fsz = max(8, int(min(r * 0.105,
                                 (inner * 1.75) / max(1, len(name)) * 1.6 - space)))
            f = px_font(fsz * 1.33, QFont.Weight.Bold)
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, space)
            p.setFont(f)
            p.setPen(QPen(blend(qcol(C.WHITE), 0.6 + 0.4 * min(1.0, amp * 2)), 1))
            p.drawText(QRectF(cx - r, cy - fsz, r * 2, fsz * 2),
                       Qt.AlignmentFlag.AlignCenter, name)

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():      # device not ready (e.g. 0-size during layout) — skip cleanly
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # The backdrop is one cached pixmap, rebuilt only when the size or the
        # theme changes — so live re-theming still repaints it.
        key = (W, H, C.PRI, C.BG, C.WHITE)
        if self._grid_cache is None or self._grid_key != key:
            self._grid_cache = self._make_grid(W, H)
            self._grid_key = key
        p.drawPixmap(0, 0, self._grid_cache)

        cx, cy = W / 2, H / 2
        fw = min(W, H)
        # The state line and waveform sit at the bottom edge so the central HUD stays movie-clean
        sy = H - 42.0
        band_t = 15.0
        band_h = max(60.0, sy - 20.0 - band_t)

        if self._avatar is not None and self.hud_style == "face":
            r_head = min(fw * 0.355, band_h / (self._avatar.SPAN + 0.08))
            head_cy = band_t + (band_h - self._avatar.SPAN * r_head) / 2.0 + r_head
            if self.muted:
                main = acc = qcol(C.MUTED_C)
            else:
                main = qcol(C.PRI)
                if self.speaking:
                    acc = qcol(C.ACC)
                elif self.state in ("THINKING", "PROCESSING"):
                    acc = qcol(C.ACC2)
                elif self.state == "LISTENING":
                    acc = qcol(C.GREEN)
                else:
                    acc = qcol(C.PRI)
            self._avatar.paint(p, cx, head_cy, r_head, main, acc, qcol(C.BG))
        elif self._reactor is not None:
            r = min(W * 0.28, (band_h) / 2.8)
            core_cy = band_t + band_h / 2.0 - 5.0
            self._paint_core(p, cx, core_cy, r, W, band_h)
        else:
            r = min(W * 0.46, band_h / 2.0)
            self._paint_core_classic(p, cx, band_t + band_h / 2.0, r, W, band_h)

        # ── Top-Left Back / Exit HUD Button ───────────────────────────────
        self._exit_btn_rect = QRectF(24.0, 18.0, 150.0, 30.0)
        is_hover_exit = bool(getattr(self, "_hover_exit", False))
        p.save()
        p.setPen(QPen(blend(C.PRI, 0.95 if is_hover_exit else 0.45), 1.2))
        p.setBrush(QBrush(QColor(255, 157, 0, 50 if is_hover_exit else 14)))
        p.drawRoundedRect(self._exit_btn_rect, 4, 4)
        p.setFont(px_font(9, QFont.Weight.Bold, mono=True, spacing=1.0))
        p.setPen(QPen(blend(C.PRI if is_hover_exit else C.TEXT, 0.95)))
        p.drawText(self._exit_btn_rect, Qt.AlignmentFlag.AlignCenter, "< WORKSTATION [ESC]")
        p.restore()

        # ── Top-Right HUD Clock (Movie accurate) ──────────────────────────
        clock_str = time.strftime("%H:%M:%S")
        date_str = time.strftime("%a %d %b %Y").upper()

        p.setFont(px_font(26, QFont.Weight.Bold, mono=True, spacing=1.2))
        p.setPen(QPen(blend(C.PRI, 0.95)))
        p.drawText(QRectF(W - 250, 18, 230, 32), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, clock_str)

        p.setFont(px_font(10, QFont.Weight.DemiBold, mono=True, spacing=1.8))
        p.setPen(QPen(blend(C.TEXT_DIM, 0.85)))
        p.drawText(QRectF(W - 250, 48, 230, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, date_str)

        # ── Left HUD System Log (Movie accurate) ──────────────────────────
        log_x, log_y = 22.0, cy - 35.0
        f_log = px_font(10, QFont.Weight.Medium, mono=True, spacing=0.8)
        p.setFont(f_log)
        for i, (ts, tag, msg) in enumerate(self._hud_logs[-5:]):
            y_pos = log_y + i * 22.0
            p.setPen(QPen(blend(C.PRI_DIM, 0.80)))
            p.drawText(QRectF(log_x, y_pos, 70, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, ts)
            p.setPen(QPen(blend(C.PRI, 0.95)))
            f_tag = px_font(10, QFont.Weight.Bold, mono=True)
            p.setFont(f_tag)
            p.drawText(QRectF(log_x + 68, y_pos, 60, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tag)
            p.setFont(f_log)
            p.setPen(QPen(blend(C.TEXT, 0.90)))
            trunc_msg = msg[:32] + "..." if len(msg) > 35 else msg
            p.drawText(QRectF(log_x + 130, y_pos, 280, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, trunc_msg)

        # ── Bottom-Right Interactive Real Map Widget ──────────────────────
        mw, mh = 168.0, 116.0
        mx = W - mw - 24.0
        my = H - mh - 30.0
        self._map_rect = QRectF(mx, my, mw, mh)

        p.save()
        p.setPen(QPen(blend(C.BORDER_B, 0.90), 1.2))
        p.setBrush(QBrush(QColor(18, 10, 2, 230)))
        p.drawRect(self._map_rect)

        p.setClipRect(QRectF(mx + 1, my + 1, mw - 2, mh - 2))

        # Render the actual real tactical street map
        if self._map_pixmap is not None and not self._map_pixmap.isNull():
            p.drawPixmap(
                QRectF(mx + 1, my + 1, mw - 2, mh - 2),
                self._map_pixmap,
                QRectF(0, 0, self._map_pixmap.width(), self._map_pixmap.height())
            )
            # Subtle amber overlay tint to match holographic HUD
            p.fillRect(QRectF(mx + 1, my + 1, mw - 2, mh - 2), QColor(255, 157, 0, 25))
        else:
            p.setPen(QPen(blend(C.PRI_DIM, 0.35), 1.0))
            for gx in range(int(mx) + 14, int(mx + mw), 22):
                p.drawLine(QLineF(gx, my, gx, my + mh))
            for gy in range(int(my) + 12, int(my + mh), 18):
                p.drawLine(QLineF(mx, gy, mx + mw, gy))

        # Real-time pulsating GPS location crosshair right in center
        blip_x, blip_y = mx + mw / 2.0, my + mh / 2.0
        pulse = 0.5 + 0.5 * math.sin(self._tick * 0.15)
        p.setPen(QPen(blend(C.WHITE, 0.95), 1.2))
        p.drawLine(QLineF(blip_x - 10, blip_y, blip_x + 10, blip_y))
        p.drawLine(QLineF(blip_x, blip_y - 10, blip_x, blip_y + 10))
        p.setPen(QPen(blend(C.ACC, 0.80), 1.0))
        p.drawEllipse(QPointF(blip_x, blip_y), 6.0 + 4.0 * pulse, 6.0 + 4.0 * pulse)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(with_alpha(C.ACC, 0.60 * pulse)))
        p.drawEllipse(QPointF(blip_x, blip_y), 3.0, 3.0)

        # Top coordinate badge
        coords_txt = self._loc_info.get("coords_str", "15.5016° N, 73.8234° E")
        p.setFont(px_font(7, QFont.Weight.Medium, mono=True))
        p.setPen(QPen(blend(C.PRI, 0.95)))
        p.drawText(QRectF(mx + 6, my + 4, mw - 12, 12), Qt.AlignmentFlag.AlignLeft, coords_txt)

        # Bottom click prompt
        p.setFont(px_font(6, QFont.Weight.Bold, mono=True, spacing=1.0))
        p.setPen(QPen(blend(C.TEXT_DIM, 0.85)))
        p.drawText(QRectF(mx + 6, my + mh - 14, mw - 12, 12), Qt.AlignmentFlag.AlignRight, "LIVE GPS LOCK")
        p.restore()

        # Real location label beneath map box
        loc_label = self._loc_info.get("label", "PANJIM, GOA")
        p.setFont(px_font(8, QFont.Weight.Bold, mono=True, spacing=1.2))
        p.setPen(QPen(blend(C.PRI, 0.95)))
        p.drawText(QRectF(mx - 20, my + mh + 4, mw + 20, 16),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   loc_label)

        # state line: spaced capitals between two fading rules that pulse
        if self.muted:
            txt, col = "MUTED", qcol(C.MUTED_C)
        elif self.speaking:
            txt, col = "SPEAKING", qcol(C.ACC)
        elif self.state in ("THINKING", "PROCESSING"):
            txt, col = self.state, qcol(C.ACC2)
        elif self.state == "LISTENING":
            txt, col = "LISTENING", qcol(C.GREEN)
        else:
            txt, col = str(self.state), qcol(C.PRI)
        p.setFont(px_font(13, QFont.Weight.DemiBold, spacing=5))
        tw = p.fontMetrics().horizontalAdvance(txt)
        p.setPen(QPen(col))
        p.drawText(QRectF(0, sy, W, 22), Qt.AlignmentFlag.AlignCenter, txt)
        pulse = 0.85 if (self._blink or self.speaking or self.muted) else 0.40
        rule = min(110.0, W * 0.12)
        for sgn in (-1, 1):
            x0 = cx + sgn * (tw / 2 + 14)
            lg = QLinearGradient(x0, 0, x0 + sgn * rule, 0)
            lg.setColorAt(0.0, with_alpha(col, pulse))
            lg.setColorAt(1.0, with_alpha(col, 0.0))
            p.setPen(QPen(QBrush(lg), 1))
            p.drawLine(QLineF(x0, sy + 11, x0 + sgn * rule, sy + 11))

        # waveform — the real audio level (the mic while listening, the voice
        # while speaking), mirrored below its baseline like a reflection
        wy = sy + 50
        N = 48
        span = min(W * 0.60, 420.0)
        bw = span / N
        amp = self._amp_disp
        mid = (N - 1) / 2.0
        wx0 = cx - span / 2
        for i in range(N):
            if self.muted:
                hgt, c = 1.5, qcol(C.MUTED_C)
            else:
                env = (1.0 - abs(i - mid) / mid) ** 0.7      # centre-weighted hump
                shimmer = 0.55 + 0.45 * math.sin(self._tick * 0.18 + i * 0.7)
                idle = 2.0 + 1.5 * math.sin(self._tick * 0.09 + i * 0.6)
                hgt = max(1.5, min(24.0, idle + amp * 22.0 * env * shimmer))
                c = (blend(col, 0.35 + 0.65 * env) if amp > 0.05
                     else blend(C.PRI, 0.28 + 0.2 * env))
            x = wx0 + i * bw
            w = max(1.5, bw - 2.0)
            p.fillRect(QRectF(x, wy - hgt, w, hgt), c)
            p.fillRect(QRectF(x, wy + 1.5, w, hgt * 0.45), blend(c, 0.30))

        p.end()   # end deterministically so the backing store never flushes an active painter
