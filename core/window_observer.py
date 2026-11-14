"""
core/window_observer.py — Active Window & Foreground Context Observer for JARVIS

Passively monitors the currently active Windows application and title
using native Win32 APIs, providing real-time software context to JARVIS.
"""
import ctypes
import os
import threading
import time
import psutil

class WindowObserver:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = WindowObserver()
            return cls._instance

    def __init__(self):
        self._running = False
        self._thread = None
        self._current_info = {
            "title": "Desktop",
            "process": "explorer.exe",
            "app_name": "Windows Desktop",
            "timestamp": time.time(),
        }

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="window-observer")
        self._thread.start()

    def stop(self):
        self._running = False

    def get_active_window(self) -> dict:
        """Returns {title, process, app_name, timestamp} for the foreground window."""
        return dict(self._current_info)

    def get_context_summary(self) -> str:
        """Brief sentence describing current user focus."""
        info = self.get_active_window()
        title = info.get("title", "")
        app = info.get("app_name", "")
        if not title or title == "Desktop":
            return "The user is on the Windows Desktop."
        return f"The user is currently focused on {app} ({title})."

    def _poll_once(self):
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return

            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.strip()

            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_name = ""
            if pid.value > 0:
                try:
                    proc = psutil.Process(pid.value)
                    proc_name = proc.name()
                except Exception:
                    pass

            app_name = proc_name.replace(".exe", "").capitalize()
            # Clean common names
            if "code" in proc_name.lower():
                app_name = "Visual Studio Code"
            elif "chrome" in proc_name.lower():
                app_name = "Google Chrome"
            elif "msedge" in proc_name.lower():
                app_name = "Microsoft Edge"
            elif "discord" in proc_name.lower():
                app_name = "Discord"
            elif "spotify" in proc_name.lower():
                app_name = "Spotify"
            elif "whis" in proc_name.lower():
                app_name = "Whis Beats"
            elif "rivals" in proc_name.lower():
                app_name = "Marvel Rivals"

            if title:
                self._current_info = {
                    "title": title,
                    "process": proc_name,
                    "app_name": app_name,
                    "timestamp": time.time(),
                }
        except Exception:
            pass

    def _poll_loop(self):
        while self._running:
            self._poll_once()
            time.sleep(1.5)
