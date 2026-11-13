"""gui/reactor.py — JARVIS MARK 2 3-D Celestial Arc Reactor Gyroscope.

Replicates the movie-accurate holographic celestial gyroscope sphere:
a radiant glowing arc-reactor core surrounded by a 3D spherical particle cloud
and rotating segmented gyroscopic orbital rings with perspective depth cueing.
"""
from __future__ import annotations

import math
import numpy as np
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient,
)

_DISPLAY = ["Bahnschrift", "Consolas", "Segoe UI", "SF Pro Display",
            "Helvetica Neue", "Noto Sans", "DejaVu Sans"]

_PITCH = math.radians(18.0)      # camera angle looking down
_CAM_D = 4.2                     # perspective distance in core radii
_N_RING = 120                    # points on high-res rings
_N_SEGS = 64                     # segmented ticks on the main dash ring
_SPHERE = 0.40                   # inner core relative radius


def _rx(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float)


def _ry(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=float)


def _rz(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)


def _with_alpha(col: QColor, a: float) -> QColor:
    c = QColor(col)
    c.setAlphaF(max(0.0, min(1.0, float(a))))
    return c


class Reactor3D:
    """3D Celestial Arc Reactor with particle sphere and gyroscopic rings."""

    TOP = 1.6
    BOTTOM = 1.6

    def __init__(self):
        # Base unit circles
        t = np.linspace(0.0, 2 * math.pi, _N_RING, endpoint=False)
        self._ring = np.vstack([np.cos(t), np.zeros_like(t), np.sin(t)])

        # Segmented equatorial ring: discrete dash lines and gap intervals
        t_dash = np.linspace(0.0, 2 * math.pi, _N_SEGS, endpoint=False)
        step = (2 * math.pi / _N_SEGS) * 0.65  # 65% dash, 35% gap
        self._dash_p1 = np.vstack([np.cos(t_dash), np.zeros_like(t_dash), np.sin(t_dash)])
        self._dash_p2 = np.vstack([np.cos(t_dash + step), np.zeros_like(t_dash), np.sin(t_dash + step)])

        # Generate 3D spherical particle cloud (starlight motes in a celestial shell)
        rng = np.random.default_rng(2026)
        n_particles = 460
        # Fibonacci / Gaussian spherical shell distribution
        phi = rng.uniform(0.0, 2 * math.pi, n_particles)
        costheta = rng.uniform(-1.0, 1.0, n_particles)
        theta = np.arccos(costheta)
        # Radii varying between 0.35 and 1.65 core radii (cluster around 0.8 - 1.4)
        r_dist = rng.uniform(0.35, 1.65, n_particles) ** 0.82
        px = r_dist * np.sin(theta) * np.cos(phi)
        py = r_dist * np.sin(theta) * np.sin(phi) * 0.92
        pz = r_dist * np.cos(theta)
        self._particle_pts = np.vstack([px, py, pz])
        self._particle_sizes = rng.uniform(0.9, 2.6, n_particles)
        self._particle_phases = rng.uniform(0.0, 2 * math.pi, n_particles)
        self._particle_speeds = rng.uniform(0.3, 1.2, n_particles)

        self.spin = 0.0
        self._view = _rx(_PITCH)

    def step(self, dt: float, speaking: bool, thinking: bool, muted: bool) -> None:
        dt = min(0.10, max(0.0, dt))
        rate = 0.15 if muted else 0.40 + (1.6 if thinking else 0.0) + (0.9 if speaking else 0.0)
        self.spin += dt * rate

    def _project(self, pts: np.ndarray, cx: float, cy: float, r: float):
        v = self._view @ pts
        denom = np.maximum(0.2, _CAM_D - v[2])
        s = _CAM_D / denom
        return cx + v[0] * s * r, cy - v[1] * s * r, v[2], s

    @staticmethod
    def _draw_cued_ring(p: QPainter, X: np.ndarray, Y: np.ndarray, Z: np.ndarray,
                         col: QColor, a_front: float, a_back: float, width: float,
                         front: bool) -> None:
        """Draw segments of a ring either in front of or behind the depth plane."""
        n = len(X)
        X_next = np.roll(X, -1)
        Y_next = np.roll(Y, -1)
        Z_next = np.roll(Z, -1)
        Z_mid = (Z + Z_next) * 0.5

        if front:
            mask = Z_mid >= 0.0
            if not mask.any():
                return
            alpha_base = a_front
        else:
            mask = Z_mid < 0.0
            if not mask.any():
                return
            alpha_base = a_back

        idx = np.flatnonzero(mask)
        lines = []
        for i in idx:
            zm = Z_mid[i]
            # depth-based brightness
            fade = 0.55 + 0.45 * max(0.0, min(1.0, zm + 1.0)) if front else 0.35 + 0.45 * max(0.0, min(1.0, zm + 1.0))
            pen = QPen(_with_alpha(col, alpha_base * fade), width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QLineF(float(X[i]), float(Y[i]), float(X_next[i]), float(Y_next[i])))

    @staticmethod
    def _draw_cued_dashes(p: QPainter, X1: np.ndarray, Y1: np.ndarray,
                          X2: np.ndarray, Y2: np.ndarray, Z: np.ndarray,
                          col: QColor, a_front: float, a_back: float, width: float,
                          front: bool) -> None:
        """Draw segmented dash ticks with depth cueing."""
        mask = (Z >= 0.0) if front else (Z < 0.0)
        idx = np.flatnonzero(mask)
        if len(idx) == 0:
            return

        alpha_base = a_front if front else a_back
        for i in idx:
            zm = Z[i]
            fade = (0.50 + 0.50 * max(0.0, min(1.0, zm + 1.0))) if front else (0.30 + 0.40 * max(0.0, min(1.0, zm + 1.0)))
            pen = QPen(_with_alpha(col, alpha_base * fade), width)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            p.setPen(pen)
            p.drawLine(QLineF(float(X1[i]), float(Y1[i]), float(X2[i]), float(Y2[i])))

    def paint(self, p: QPainter, cx: float, cy: float, r: float, main: QColor,
              acc: QColor, white: QColor, amp: float, live: bool, name: str = "") -> None:
        spin = self.spin
        amp = max(0.0, min(1.0, amp))

        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # ── 1. Rotate 3D Gyroscopic Rings ────────────────────────────────────
        # Ring 1: Primary Equatorial Segmented Tilted Ring (~20 deg tilt)
        r1_rot = _ry(spin * 0.85) @ _rx(math.radians(22.0))
        pts_r1 = r1_rot @ (self._ring * 1.34)
        X_r1, Y_r1, Z_r1, s_r1 = self._project(pts_r1, cx, cy, r)

        # Segmented dashes for Ring 1
        d1_p1 = r1_rot @ (self._dash_p1 * 1.34)
        d1_p2 = r1_rot @ (self._dash_p2 * 1.34)
        X_d1_1, Y_d1_1, Z_d1, _ = self._project(d1_p1, cx, cy, r)
        X_d1_2, Y_d1_2, _, _ = self._project(d1_p2, cx, cy, r)

        # Ring 2: Inclined Gyroscope Ring (tilted ~64 deg)
        r2_rot = _ry(-spin * 1.15) @ _rz(math.radians(64.0)) @ _rx(math.radians(18.0))
        pts_r2 = r2_rot @ (self._ring * 1.16)
        X_r2, Y_r2, Z_r2, _ = self._project(pts_r2, cx, cy, r)

        # Ring 3: Counter-inclined Gyroscope Ring (~ -52 deg)
        r3_rot = _ry(spin * 1.30) @ _rx(math.radians(-54.0)) @ _rz(math.radians(15.0))
        pts_r3 = r3_rot @ (self._ring * 0.94)
        X_r3, Y_r3, Z_r3, _ = self._project(pts_r3, cx, cy, r)

        # Ring 4: Outer Celestial Meridian Ring
        r4_rot = _ry(spin * 0.45) @ _rx(math.radians(10.0))
        pts_r4 = r4_rot @ (self._ring * 1.52)
        X_r4, Y_r4, Z_r4, _ = self._project(pts_r4, cx, cy, r)

        # ── 2. Rotate 3D Particle Cloud ──────────────────────────────────────
        part_rot = _ry(spin * 0.50) @ _rx(math.radians(15.0))
        pts_p = part_rot @ self._particle_pts
        PX, PY, PZ, PS = self._project(pts_p, cx, cy, r)

        # ── 3. DRAW BACK ELEMENTS (Z < 0) ────────────────────────────────────
        # Back rings
        self._draw_cued_ring(p, X_r4, Y_r4, Z_r4, main, 0.45, 0.18, 1.0, front=False)
        self._draw_cued_ring(p, X_r2, Y_r2, Z_r2, acc, 0.75, 0.25, 1.4, front=False)
        self._draw_cued_ring(p, X_r3, Y_r3, Z_r3, main, 0.65, 0.22, 1.2, front=False)
        # Back segmented equatorial ring
        self._draw_cued_dashes(p, X_d1_1, Y_d1_1, X_d1_2, Y_d1_2, Z_d1, acc if live else main,
                               0.85, 0.28, 2.0, front=False)

        # Back particles (dimmer, smaller)
        p.setPen(Qt.PenStyle.NoPen)
        back_mask = PZ < 0.0
        back_idx = np.flatnonzero(back_mask)
        for i in back_idx:
            zm = float(PZ[i])
            fade = 0.15 + 0.35 * max(0.0, min(1.0, zm + 1.2))
            twinkle = 0.70 + 0.30 * math.sin(spin * self._particle_speeds[i] * 4.0 + self._particle_phases[i])
            alpha = fade * twinkle * (0.8 + 0.4 * amp)
            col_p = _with_alpha(acc if (i % 5 == 0) else main, alpha)
            rad = max(0.8, self._particle_sizes[i] * float(PS[i]) * 0.75)
            p.setBrush(QBrush(col_p))
            p.drawEllipse(QPointF(float(PX[i]), float(PY[i])), rad, rad)

        # ── 4. DRAW THE GLOWING CELESTIAL ARC REACTOR CORE ───────────────────
        sr = r * _SPHERE * (1.0 + 0.18 * amp)

        # Outer fiery atmospheric halo
        corona_r = sr * 2.85
        corona = QRadialGradient(cx, cy, corona_r)
        corona.setColorAt(0.0, _with_alpha(acc, 0.35 + 0.25 * amp))
        corona.setColorAt(0.35, _with_alpha(main, 0.18 + 0.18 * amp))
        corona.setColorAt(0.70, _with_alpha(main, 0.05))
        corona.setColorAt(1.0, _with_alpha(main, 0.0))
        p.setBrush(QBrush(corona))
        p.drawEllipse(QPointF(cx, cy), corona_r, corona_r)

        # 10 Toroidal Magnetic Confinement Induction Coils around reactor boundary
        coil_r_in = sr * 0.95
        coil_r_out = sr * 1.34
        for k in range(10):
            angle = (k * 2.0 * math.pi / 10.0) + spin * 0.14
            c_cos, c_sin = math.cos(angle), math.sin(angle)
            p1_x = cx + coil_r_in * c_cos
            p1_y = cy + coil_r_in * c_sin
            p2_x = cx + coil_r_out * c_cos
            p2_y = cy + coil_r_out * c_sin

            # Heavy magnetic stator bracket body
            p.setPen(QPen(_with_alpha(main, 0.40 + 0.35 * amp), 3.8))
            p.drawLine(QLineF(p1_x, p1_y, p2_x, p2_y))

            # Radiant copper-gold induction windings
            p.setPen(QPen(_with_alpha(acc, 0.75 + 0.25 * amp), 1.8))
            p.drawLine(QLineF(p1_x, p1_y, p2_x, p2_y))

            # Outer magnetic capacitor tip nodes
            tip_x = cx + (coil_r_out + 2.8) * c_cos
            tip_y = cy + (coil_r_out + 2.8) * c_sin
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(_with_alpha(white if (k % 2 == 0) else acc, 0.88)))
            p.drawEllipse(QPointF(tip_x, tip_y), 2.0, 2.0)

        # Concentric Technical Stator Telemetry Ring with 36 micro-hash ticks
        stator_r = sr * 0.92
        p.setPen(QPen(_with_alpha(main, 0.35 + 0.25 * amp), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), stator_r, stator_r)
        p.drawEllipse(QPointF(cx, cy), stator_r * 0.72, stator_r * 0.72)

        for t_idx in range(36):
            t_ang = (t_idx * 2.0 * math.pi / 36.0) - spin * 0.16
            t_cos, t_sin = math.cos(t_ang), math.sin(t_ang)
            t_len = 5.5 if (t_idx % 9 == 0) else (3.2 if (t_idx % 3 == 0) else 1.8)
            p.setPen(QPen(_with_alpha(acc if (t_idx % 9 == 0) else main, 0.70 if (t_idx % 9 == 0) else 0.35), 1.0))
            p.drawLine(QLineF(cx + (stator_r - t_len) * t_cos, cy + (stator_r - t_len) * t_sin,
                              cx + stator_r * t_cos, cy + stator_r * t_sin))

        # Dynamic Plasma Micro-Lightning Discharge Filaments
        if live or amp > 0.03:
            p.setPen(QPen(_with_alpha(white, 0.80 * min(1.0, amp * 1.6 + 0.35)), 1.3))
            for f_idx in range(5):
                f_ang = (f_idx * 2.0 * math.pi / 5.0) + spin * 1.6 + math.sin(spin * 5.0 + f_idx) * 0.35
                f_cos, f_sin = math.cos(f_ang), math.sin(f_ang)
                m_r = sr * (0.35 + 0.25 * math.sin(spin * 3.5 + f_idx))
                m_x = cx + m_r * f_cos + math.sin(spin * 12.0 + f_idx) * 3.5
                m_y = cy + m_r * f_sin + math.cos(spin * 12.0 + f_idx) * 3.5
                t_x = cx + stator_r * f_cos
                t_y = cy + stator_r * f_sin
                p.drawLine(QLineF(cx, cy, m_x, m_y))
                p.drawLine(QLineF(m_x, m_y, t_x, t_y))

        # Radiant spherical core
        core_grad = QRadialGradient(QPointF(cx, cy), sr, QPointF(cx - sr * 0.15, cy - sr * 0.20))
        core_grad.setColorAt(0.0, _with_alpha(white, 0.98))
        core_grad.setColorAt(0.20, _with_alpha(white, 0.88))
        core_grad.setColorAt(0.50, _with_alpha(acc, 0.80 + 0.20 * amp))
        core_grad.setColorAt(0.85, _with_alpha(main, 0.38))
        core_grad.setColorAt(1.0, _with_alpha(main, 0.06))
        p.setBrush(QBrush(core_grad))
        p.drawEllipse(QPointF(cx, cy), sr, sr)

        # Central white-hot nuclear heart
        heart_r = sr * (0.28 + 0.22 * amp)
        heart = QRadialGradient(cx, cy, heart_r)
        heart.setColorAt(0.0, _with_alpha(white, 1.0))
        heart.setColorAt(0.55, _with_alpha(white, 0.90))
        heart.setColorAt(0.85, _with_alpha(acc, 0.45))
        heart.setColorAt(1.0, _with_alpha(acc, 0.0))
        p.setBrush(QBrush(heart))
        p.drawEllipse(QPointF(cx, cy), heart_r, heart_r)

        # Spherical glass refraction highlight on upper-left quadrant
        spec_grad = QRadialGradient(cx - sr * 0.32, cy - sr * 0.32, sr * 0.60)
        spec_grad.setColorAt(0.0, _with_alpha(white, 0.42 + 0.20 * amp))
        spec_grad.setColorAt(0.50, _with_alpha(white, 0.12))
        spec_grad.setColorAt(1.0, _with_alpha(white, 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(spec_grad))
        p.drawEllipse(QPointF(cx - sr * 0.28, cy - sr * 0.28), sr * 0.52, sr * 0.35)

        # Horizontal anamorphic cinematic lens flare across reactor core
        flare_w = r * 1.85 * (1.0 + 0.30 * amp)
        flare_h = max(2.5, 3.5 + 7.5 * amp)
        flare_grad = QLinearGradient(cx - flare_w, cy, cx + flare_w, cy)
        flare_grad.setColorAt(0.0, _with_alpha(acc, 0.0))
        flare_grad.setColorAt(0.25, _with_alpha(acc, 0.12 + 0.15 * amp))
        flare_grad.setColorAt(0.48, _with_alpha(white, 0.55 + 0.40 * amp))
        flare_grad.setColorAt(0.50, _with_alpha(white, 0.95))
        flare_grad.setColorAt(0.52, _with_alpha(white, 0.55 + 0.40 * amp))
        flare_grad.setColorAt(0.75, _with_alpha(acc, 0.12 + 0.15 * amp))
        flare_grad.setColorAt(1.0, _with_alpha(acc, 0.0))
        p.setBrush(QBrush(flare_grad))
        p.drawRect(QRectF(cx - flare_w, cy - flare_h * 0.5, flare_w * 2.0, flare_h))

        # ── 5. DRAW FRONT ELEMENTS (Z >= 0) ──────────────────────────────────
        # Front particles (bright, sparkling, depth-amplified)
        front_mask = PZ >= 0.0
        front_idx = np.flatnonzero(front_mask)
        for i in front_idx:
            zm = float(PZ[i])
            fade = 0.50 + 0.50 * max(0.0, min(1.0, zm * 0.8 + 0.2))
            twinkle = 0.75 + 0.25 * math.sin(spin * self._particle_speeds[i] * 5.0 + self._particle_phases[i])
            alpha = min(1.0, fade * twinkle * (0.85 + 0.45 * amp))
            is_white = (i % 7 == 0)
            col_p = _with_alpha(white if is_white else (acc if (i % 3 == 0) else main), alpha)
            rad = max(1.1, self._particle_sizes[i] * float(PS[i]) * 0.95)
            p.setBrush(QBrush(col_p))
            p.drawEllipse(QPointF(float(PX[i]), float(PY[i])), rad, rad)

        # Front gyroscopic rings
        self._draw_cued_ring(p, X_r3, Y_r3, Z_r3, main, 0.70, 0.22, 1.3, front=True)
        self._draw_cued_ring(p, X_r2, Y_r2, Z_r2, acc, 0.85, 0.25, 1.6, front=True)
        # Front segmented equatorial ring (bright & crisp)
        self._draw_cued_dashes(p, X_d1_1, Y_d1_1, X_d1_2, Y_d1_2, Z_d1,
                               acc if live else main, 0.95, 0.28, 2.2, front=True)
        self._draw_cued_ring(p, X_r4, Y_r4, Z_r4, main, 0.55, 0.18, 1.0, front=True)

        # ── 6. ORBITING TRACER BEACONS ON EQUATORIAL RING ───────────────────
        for k in range(4):
            idx = int((k * _N_RING / 4 + spin * 9.0) % _N_RING)
            depth = float(Z_r1[idx])
            tx, ty = float(X_r1[idx]), float(Y_r1[idx])
            t_rad = (2.6 + 2.0 * max(0.0, depth)) * 2.2
            tg = QRadialGradient(tx, ty, t_rad)
            alpha_tr = 0.95 if depth >= 0 else 0.45
            tg.setColorAt(0.0, _with_alpha(white, alpha_tr))
            tg.setColorAt(0.35, _with_alpha(acc, alpha_tr * 0.8))
            tg.setColorAt(1.0, _with_alpha(acc, 0.0))
            p.setBrush(QBrush(tg))
            p.drawEllipse(QPointF(tx, ty), t_rad, t_rad)

        p.restore()
