"""actions/close_app.py — Dedicated Application Closer for JARVIS

Closes applications by name (e.g., 'close Chrome', 'quit Notepad', 'exit Whis Beats',
'close Marvel Rivals') or closes the currently active/focused window.
"""
from __future__ import annotations

import os
import subprocess
from core import appidentity, outcome
from core.window_observer import WindowObserver

def close_application(parameters: dict, player=None, session_memory=None) -> str:
    """Close an application by name or close the currently active window."""
    app_name = str(parameters.get("app_name") or "").strip()

    # If user asks to close "this window", "current window", "active app"
    if not app_name or app_name.lower() in ("this", "current", "active", "this window", "active window"):
        obs = WindowObserver.get_instance()
        active = obs.get_active_window()
        app_name = active.get("app_name") or active.get("process") or ""
        if not app_name or "python" in app_name.lower() or "jarvis" in app_name.lower():
            return "I will not close the active window as it appears to be my own interface, sir."

    clean_name = app_name.lower().replace(".exe", "").strip()

    # Protect JARVIS from closing itself
    if "jarvis" in clean_name or "main.py" in clean_name:
        return "I will not close myself, sir. You can minimize or exit my window manually."

    if player:
        player.write_log(f"SYS: Requesting close for '{app_name}'...")

    # 1. Use appidentity to find running matches
    matches = appidentity.running(clean_name)
    if matches:
        closed_count = 0
        for m in matches:
            if m.is_self or m.pid == os.getpid():
                continue
            gone, _ = appidentity.request_close(m)
            if gone:
                closed_count += 1

        if closed_count > 0:
            if player:
                player.write_log(f"SYS: Successfully closed {app_name}.")
            return f"Closed {app_name}, sir."

    # 2. Windows Taskkill fallback for obstinate processes or custom app names
    try:
        # Check matching processes
        import psutil
        matched_procs = []
        for p in psutil.process_iter(['pid', 'name']):
            p_name = p.info['name'].lower()
            if clean_name in p_name:
                matched_procs.append(p.info['name'])
        
        if matched_procs:
            for proc_name in set(matched_procs):
                subprocess.run(["taskkill", "/F", "/IM", proc_name],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if player:
                player.write_log(f"SYS: Terminated process {app_name}.")
            return f"Closed {app_name}, sir."
    except Exception as e:
        print(f"[CloseApp] Taskkill error: {e}")

    return f"I could not find an active window or running process for '{app_name}', sir."


TOOL = {
    "name": "close_app",
    "description": (
        "Closes or quits an application or program by name (e.g. 'close Chrome', 'quit Whis Beats', "
        "'exit Notepad', 'close Marvel Rivals', 'close this window'). "
        "Put the application's name in 'app_name'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {
                "type": "STRING",
                "description": "Name of the application or window to close (e.g. 'chrome', 'whis beats', 'notepad', 'current')."
            }
        },
        "required": ["app_name"],
    },
    "handler": close_application,
}
