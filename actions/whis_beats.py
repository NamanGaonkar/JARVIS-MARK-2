"""
actions/whis_beats.py — Native WHIS BEATS & System Media Controller for JARVIS

Controls Naman's WHIS BEATS media player (and Windows media playback)
including play, pause, track skipping, and volume control.
"""
import ctypes
import os
import subprocess
from pathlib import Path

WHIS_BEATS_PATH = Path(r"C:\Users\Naman Gaonkar\AppData\Local\Programs\WHIS BEATS\whis-beats.exe")
WHIS_STREAM_PATH = Path(r"C:\Users\Naman Gaonkar\AppData\Local\Programs\WHIS STREAM\WHIS STREAM.exe")

# Windows Virtual-Key Codes for Media
VK_VOLUME_MUTE         = 0xAD
VK_VOLUME_DOWN         = 0xAE
VK_VOLUME_UP           = 0xAF
VK_MEDIA_NEXT_TRACK    = 0xB0
VK_MEDIA_PREV_TRACK    = 0xB1
VK_MEDIA_STOP          = 0xB2
VK_MEDIA_PLAY_PAUSE    = 0xB3

KEYEVENTF_KEYUP = 0x0002

def _send_media_key(vk_code: int) -> None:
    """Send a hardware media key press and release event."""
    try:
        user32 = ctypes.windll.user32
        user32.keybd_event(vk_code, 0, 0, 0)
        user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
    except Exception as e:
        print(f"[WhisBeats] Key event error: {e}")

def whis_beats_control(parameters: dict, player=None, session_memory=None) -> str:
    """Execute media control actions for Whis Beats and Windows Media."""
    action = str(parameters.get("action", "toggle")).lower().strip()
    
    if action in ("open", "launch", "start"):
        if WHIS_BEATS_PATH.exists():
            try:
                os.startfile(str(WHIS_BEATS_PATH))
                if player:
                    player.write_log("WHIS BEATS: Launched player.")
                return "WHIS BEATS is now open, sir."
            except Exception as e:
                return f"Could not launch WHIS BEATS: {e}"
        else:
            return "WHIS BEATS executable was not found on your desktop installation."

    elif action in ("open_stream", "stream"):
        if WHIS_STREAM_PATH.exists():
            try:
                os.startfile(str(WHIS_STREAM_PATH))
                if player:
                    player.write_log("WHIS STREAM: Launched stream.")
                return "WHIS STREAM is now open, sir."
            except Exception as e:
                return f"Could not launch WHIS STREAM: {e}"
        else:
            return "WHIS STREAM executable was not found."

    elif action in ("play", "pause", "toggle", "play_pause"):
        _send_media_key(VK_MEDIA_PLAY_PAUSE)
        if player:
            player.write_log("WHIS BEATS: Play/Pause toggled.")
        return "Toggled playback on Whis Beats."

    elif action in ("next", "skip", "next_track"):
        _send_media_key(VK_MEDIA_NEXT_TRACK)
        if player:
            player.write_log("WHIS BEATS: Skipped to next track.")
        return "Skipped to next track on Whis Beats."

    elif action in ("previous", "prev", "back", "previous_track"):
        _send_media_key(VK_MEDIA_PREV_TRACK)
        if player:
            player.write_log("WHIS BEATS: Returned to previous track.")
        return "Playing previous track on Whis Beats."

    elif action in ("stop",):
        _send_media_key(VK_MEDIA_STOP)
        if player:
            player.write_log("WHIS BEATS: Playback stopped.")
        return "Stopped playback on Whis Beats."

    elif action in ("volume_up", "louder"):
        for _ in range(3):
            _send_media_key(VK_VOLUME_UP)
        if player:
            player.write_log("MEDIA: Volume increased.")
        return "Volume increased."

    elif action in ("volume_down", "quieter"):
        for _ in range(3):
            _send_media_key(VK_VOLUME_DOWN)
        if player:
            player.write_log("MEDIA: Volume decreased.")
        return "Volume decreased."

    elif action in ("mute", "unmute"):
        _send_media_key(VK_VOLUME_MUTE)
        if player:
            player.write_log("MEDIA: Mute toggled.")
        return "Toggled media mute."

    return f"Unknown action '{action}' for Whis Beats."

TOOL = {
    "name": "whis_beats_control",
    "description": (
        "Controls Naman's WHIS BEATS media player and Windows audio. "
        "Supports opening Whis Beats or Whis Stream, play/pause, skipping to next track, "
        "going to previous track, volume up/down, and mute."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": [
                    "open", "open_stream", "play_pause", "next", "previous",
                    "stop", "volume_up", "volume_down", "mute"
                ],
                "description": "The playback or media action to perform."
            }
        },
        "required": ["action"],
    },
    "handler": whis_beats_control,
}
