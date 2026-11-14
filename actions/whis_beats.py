"""actions/whis_beats.py — Native WHIS BEATS & Universal Media Controller for JARVIS

Controls Naman's WHIS BEATS media player, universal music search & playback,
and Windows media controls (play, pause, next, previous, volume, mute).
"""
import ctypes
import os
import subprocess
import urllib.parse
import webbrowser
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


def _play_song_online(song_name: str) -> bool:
    """Find and play the song online (YouTube / YouTube Music) immediately."""
    try:
        from actions.youtube_video import _scrape_first_video_url, _open_url
        video_url = _scrape_first_video_url(song_name)
        if video_url:
            _open_url(video_url)
            return True
    except Exception as e:
        print(f"[WhisBeats] Scrape error: {e}")

    # Fallback to direct search URL
    try:
        encoded = urllib.parse.quote_plus(song_name)
        yt_music_url = f"https://music.youtube.com/search?q={encoded}"
        webbrowser.open_new_tab(yt_music_url)
        return True
    except Exception:
        return False


def whis_beats_control(parameters: dict, player=None, session_memory=None) -> str:
    """Execute media control actions for Whis Beats, universal music playback, and Windows audio."""
    action = str(parameters.get("action", "play_pause")).lower().strip()
    query = str(parameters.get("query") or parameters.get("song") or "").strip()

    # 1. Search & Play Song
    if query or action in ("play_song", "search_and_play", "search"):
        song_target = query or action
        if player:
            player.write_log(f"MUSIC: Searching and playing '{song_target}'...")

        # If Whis Beats executable exists, ensure it's launched as the user's primary player
        if WHIS_BEATS_PATH.exists():
            try:
                os.startfile(str(WHIS_BEATS_PATH))
            except Exception:
                pass

        success = _play_song_online(song_target)
        if success:
            if player:
                player.write_log(f"MUSIC: Now playing '{song_target}'.")
            return f"Playing {song_target} now, sir."
        return f"I searched for {song_target}, sir, but could not initiate playback."

    # 2. Launch applications
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

    # 3. Hardware media playback controls
    elif action in ("play", "pause", "toggle", "play_pause"):
        _send_media_key(VK_MEDIA_PLAY_PAUSE)
        if player:
            player.write_log("WHIS BEATS: Play/Pause toggled.")
        return "Toggled playback."

    elif action in ("next", "skip", "next_track"):
        _send_media_key(VK_MEDIA_NEXT_TRACK)
        if player:
            player.write_log("WHIS BEATS: Skipped to next track.")
        return "Skipped to next track."

    elif action in ("previous", "prev", "back", "previous_track"):
        _send_media_key(VK_MEDIA_PREV_TRACK)
        if player:
            player.write_log("WHIS BEATS: Returned to previous track.")
        return "Playing previous track."

    elif action in ("stop",):
        _send_media_key(VK_MEDIA_STOP)
        if player:
            player.write_log("WHIS BEATS: Playback stopped.")
        return "Stopped playback."

    elif action in ("volume_up", "louder"):
        for _ in range(4):
            _send_media_key(VK_VOLUME_UP)
        if player:
            player.write_log("MEDIA: Volume increased.")
        return "Volume increased."

    elif action in ("volume_down", "quieter"):
        for _ in range(4):
            _send_media_key(VK_VOLUME_DOWN)
        if player:
            player.write_log("MEDIA: Volume decreased.")
        return "Volume decreased."

    elif action in ("mute", "unmute"):
        _send_media_key(VK_VOLUME_MUTE)
        if player:
            player.write_log("MEDIA: Mute toggled.")
        return "Toggled media mute."

    return f"Unknown action '{action}' for media controller."


TOOL = {
    "name": "whis_beats_control",
    "description": (
        "Controls WHIS BEATS and universal music/video playback. "
        "Use action='play_song' with 'query' (e.g. 'Cutiepie', 'Believer Imagine Dragons') "
        "to search and play ANY song, track, or music video immediately. "
        "Also supports: play_pause, next, previous, stop, volume_up, volume_down, mute, "
        "and opening Whis Beats or Whis Stream."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": [
                    "play_song", "play_pause", "play", "pause", "next", "previous",
                    "stop", "volume_up", "volume_down", "mute", "open", "open_stream"
                ],
                "description": "The playback, search, or media action to perform."
            },
            "query": {
                "type": "STRING",
                "description": "Song title, artist, or music query to search and play (e.g. 'Cutiepie', 'Shape of You')."
            }
        },
        "required": ["action"],
    },
    "handler": whis_beats_control,
}
