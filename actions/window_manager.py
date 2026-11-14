"""actions/window_manager.py — Window Layout, Tiling, and Snapping Controller for JARVIS

Controls desktop window positioning: snap windows left/right, tile applications side-by-side
(e.g., 'put Chrome on the left and VS Code on the right'), maximize, minimize, or center.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import time
from typing import Optional

from core import appidentity
from core.window_observer import WindowObserver

user32 = ctypes.windll.user32

SW_RESTORE   = 9
SW_MAXIMIZE  = 3
SW_MINIMIZE  = 6
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040


def _get_work_area() -> tuple[int, int, int, int]:
    """Get the usable desktop work area (excluding taskbar). Returns (x, y, w, h)."""
    class RECT(ctypes.Structure):
        _fields_ = [('left', ctypes.c_long),
                    ('top', ctypes.c_long),
                    ('right', ctypes.c_long),
                    ('bottom', ctypes.c_long)]

    rect = RECT()
    # SPI_GETWORKAREA = 0x0030
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    return rect.left, rect.top, w, h


def _find_window_hwnd(app_or_title: str) -> Optional[int]:
    """Find the top-level HWND matching the application name or window title."""
    target = app_or_title.lower().strip()
    if not target or target in ("this", "current", "active"):
        return user32.GetForegroundWindow()

    found_hwnd = []

    def enum_windows_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.lower()
                if target in title:
                    found_hwnd.append(hwnd)
                    return False  # stop enumeration
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    cb = WNDENUMPROC(enum_windows_cb)
    user32.EnumWindows(cb, 0)

    if found_hwnd:
        return found_hwnd[0]

    # Try matching by process name via psutil
    try:
        import psutil
        for p in psutil.process_iter(['pid', 'name']):
            if target in p.info['name'].lower():
                def proc_cb(hwnd, _):
                    if user32.IsWindowVisible(hwnd):
                        pid = ctypes.c_ulong()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        if pid.value == p.info['pid']:
                            found_hwnd.append(hwnd)
                            return False
                    return True
                user32.EnumWindows(WNDENUMPROC(proc_cb), 0)
                if found_hwnd:
                    return found_hwnd[0]
    except Exception:
        pass

    return None


def _set_window_rect(hwnd: int, x: int, y: int, w: int, h: int) -> bool:
    """Restore and place the window at the specified coordinates."""
    try:
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.05)
        user32.SetWindowPos(hwnd, 0, x, y, w, h, SWP_NOZORDER | SWP_SHOWWINDOW)
        return True
    except Exception as e:
        print(f"[WindowManager] SetWindowPos error: {e}")
        return False


def _ensure_app_running(app_name: str) -> None:
    """Ensure an application is running; launch it if not."""
    matches = appidentity.running(app_name)
    if not matches:
        try:
            from actions.open_app import open_app
            open_app({"app_name": app_name})
            time.sleep(1.5)
        except Exception:
            pass


def manage_window_layout(parameters: dict, player=None, session_memory=None) -> str:
    """Position, snap, or tile desktop windows."""
    action = str(parameters.get("action", "snap")).lower().strip()
    pos = str(parameters.get("position", "")).lower().strip()
    app_name = str(parameters.get("window_name") or parameters.get("app_name") or "").strip()
    left_app = str(parameters.get("left_window") or "").strip()
    right_app = str(parameters.get("right_window") or "").strip()

    x_base, y_base, screen_w, screen_h = _get_work_area()
    half_w = screen_w // 2

    # 1. Tile Side-by-Side (Split screen)
    if left_app and right_app or action in ("tile", "side_by_side", "split_screen"):
        if not left_app or not right_app:
            return "Please specify both the left and right applications to tile, sir."

        if player:
            player.write_log(f"WINDOW: Tiling {left_app} (left) & {right_app} (right)...")

        _ensure_app_running(left_app)
        _ensure_app_running(right_app)
        time.sleep(0.5)

        hwnd_left = _find_window_hwnd(left_app)
        hwnd_right = _find_window_hwnd(right_app)

        success_count = 0
        if hwnd_left:
            if _set_window_rect(hwnd_left, x_base, y_base, half_w, screen_h):
                success_count += 1
        if hwnd_right:
            if _set_window_rect(hwnd_right, x_base + half_w, y_base, half_w, screen_h):
                success_count += 1

        if success_count == 2:
            return f"Arranged {left_app} on the left and {right_app} on the right, sir."
        elif success_count == 1:
            return f"Positioned one window, but could not attach the second."
        return f"Could not find or position the windows for {left_app} and {right_app}."

    # 2. Single Window Snap / Move
    hwnd = _find_window_hwnd(app_name) if app_name else user32.GetForegroundWindow()
    if not hwnd or hwnd == 0:
        active_title = WindowObserver.get_instance().get_active_window().get("title", "")
        if active_title:
            hwnd = _find_window_hwnd(active_title)

    if not hwnd:
        return f"Could not locate an active window for '{app_name or 'current workspace'}', sir."

    label = app_name or "active window"

    if pos in ("left", "half-left", "side-left"):
        _set_window_rect(hwnd, x_base, y_base, half_w, screen_h)
        return f"Snapped {label} to the left half, sir."

    elif pos in ("right", "half-right", "side-right"):
        _set_window_rect(hwnd, x_base + half_w, y_base, half_w, screen_h)
        return f"Snapped {label} to the right half, sir."

    elif pos in ("top", "top-half"):
        _set_window_rect(hwnd, x_base, y_base, screen_w, screen_h // 2)
        return f"Snapped {label} to the top half, sir."

    elif pos in ("bottom", "bottom-half"):
        _set_window_rect(hwnd, x_base, y_base + (screen_h // 2), screen_w, screen_h // 2)
        return f"Snapped {label} to the bottom half, sir."

    elif pos in ("max", "maximize", "fullscreen"):
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        return f"Maximized {label}, sir."

    elif pos in ("min", "minimize"):
        user32.ShowWindow(hwnd, SW_MINIMIZE)
        return f"Minimized {label}, sir."

    elif pos in ("center", "middle"):
        cw = int(screen_w * 0.7)
        ch = int(screen_h * 0.7)
        cx = x_base + (screen_w - cw) // 2
        cy = y_base + (screen_h - ch) // 2
        _set_window_rect(hwnd, cx, cy, cw, ch)
        return f"Centered {label} on screen, sir."

    return f"Window position '{pos}' not recognized. Use left, right, top, bottom, maximize, or minimize."


TOOL = {
    "name": "manage_window_layout",
    "description": (
        "Controls window placement, snapping, and split-screen layouts. "
        "Use to snap windows left or right ('snap this to the left', 'maximize Chrome'), "
        "or tile two applications side-by-side ('open Chrome on the left and VS Code on the right', "
        "'put this on the left and that on the right')."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["snap", "tile", "split_screen", "maximize", "minimize"],
                "description": "Layout action to perform."
            },
            "position": {
                "type": "STRING",
                "enum": ["left", "right", "top", "bottom", "maximize", "minimize", "center"],
                "description": "Screen position for single window snap."
            },
            "window_name": {
                "type": "STRING",
                "description": "Name or title of the window/app to move (or omit for active window)."
            },
            "left_window": {
                "type": "STRING",
                "description": "For side_by_side tiling: application name for the left half."
            },
            "right_window": {
                "type": "STRING",
                "description": "For side_by_side tiling: application name for the right half."
            }
        },
        "required": ["action"],
    },
    "handler": manage_window_layout,
}
