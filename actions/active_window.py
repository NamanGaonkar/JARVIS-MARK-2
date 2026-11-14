"""
actions/active_window.py — Active Window & Foreground Application Query for JARVIS
"""
from core.window_observer import WindowObserver

def get_active_window(parameters: dict, player=None, session_memory=None) -> str:
    """Returns details on what application or window the user is currently focused on."""
    obs = WindowObserver.get_instance()
    info = obs.get_active_window()
    title = info.get("title", "Desktop")
    app = info.get("app_name", "Windows Desktop")
    proc = info.get("process", "")

    if player:
        player.write_log(f"CONTEXT: Active window is {app} ({title})")

    return f"The active foreground window is '{title}' in application '{app}' (process: {proc})."

TOOL = {
    "name": "get_active_window",
    "description": (
        "Returns the title and application name of the active foreground window "
        "that the user is currently looking at or typing in on their PC."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    },
    "handler": get_active_window,
}
