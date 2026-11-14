"""Audio listener and identifier for JARVIS.

Captures system audio loopback (Stereo Mix / WASAPI loopback) or active audio
and uses Gemini to identify songs, recognize music, or summarize what is playing in a video or stream.
"""
from __future__ import annotations

import io
import wave
import numpy as np
import sounddevice as sd
from google.genai import types

from core import gemini

def _find_loopback_device() -> tuple[int | None, int, int]:
    """Find the best audio device for loopback capture.
    Returns (device_index, samplerate, channels).
    """
    devices = sd.query_devices()
    
    # 1. Search for Stereo Mix / What U Hear
    for idx, d in enumerate(devices):
        if d.get("max_input_channels", 0) > 0:
            name = d.get("name", "").lower()
            if "stereo mix" in name or "what u hear" in name or "wave out" in name:
                sr = int(d.get("default_samplerate", 48000))
                ch = min(2, d.get("max_input_channels", 2))
                return idx, sr, ch
                
    # 2. Fallback to default input
    default_in = sd.default.device[0]
    if default_in is not None and default_in >= 0:
        d = devices[default_in]
        sr = int(d.get("default_samplerate", 48000))
        ch = min(2, d.get("max_input_channels", 1))
        return default_in, sr, ch

    return None, 44100, 1


def _record_audio(device_idx: int | None, sr: int, ch: int, duration_sec: float) -> np.ndarray | None:
    """Record audio synchronously from the specified device."""
    total_frames = int(sr * duration_sec)
    try:
        data = sd.rec(total_frames, samplerate=sr, channels=ch, device=device_idx, dtype="float32")
        sd.wait()
        return data
    except Exception as e:
        print(f"[AudioListener] Recording error on device {device_idx}: {e}")
        return None


def _to_wav_bytes(audio_data: np.ndarray, sr: int) -> bytes:
    """Convert float32 numpy array to 16-bit mono WAV bytes."""
    # Convert to mono if multi-channel to save bandwidth
    if audio_data.ndim > 1 and audio_data.shape[1] > 1:
        mono = np.mean(audio_data, axis=1)
    else:
        mono = audio_data.flatten()

    # Peak normalization so even quiet songs/videos are crystal clear to Gemini
    peak = float(np.max(np.abs(mono)))
    if peak > 0:
        mono = mono * (0.85 / peak)

    clamped = np.clip(mono, -1.0, 1.0)
    int16_data = (clamped * 32767.0).astype(np.int16)

    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int16_data.tobytes())
    return bio.getvalue()


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Listen to current desktop loopback audio and describe/identify it."""
    query = str(parameters.get("query") or "What is currently playing?").strip()
    seconds = int(parameters.get("seconds") or 5)
    seconds = max(3, min(10, seconds))

    if player:
        player.write_log("SYS", f"Capturing {seconds}s of system audio loopback...")

    dev_idx, sr, ch = _find_loopback_device()
    audio_array = _record_audio(dev_idx, sr, ch, seconds) if dev_idx is not None else None

    peak = float(np.max(np.abs(audio_array))) if audio_array is not None else 0.0

    # Fallback to microphone if loopback is completely silent (e.g. speakers playing in room)
    if peak < 0.001:
        default_mic = sd.default.device[0]
        if default_mic is not None and default_mic >= 0 and default_mic != dev_idx:
            try:
                mic_dev = sd.query_devices(default_mic)
                mic_sr = int(mic_dev.get("default_samplerate", 48000))
                mic_audio = _record_audio(default_mic, mic_sr, 1, seconds)
                if mic_audio is not None and float(np.max(np.abs(mic_audio))) > peak:
                    audio_array = mic_audio
                    sr = mic_sr
                    peak = float(np.max(np.abs(audio_array)))
            except Exception:
                pass

    if audio_array is None or peak < 0.0003:
        if player:
            player.write_log("SYS", "Audio loopback captured silence.")
        return "It sounds quiet right now, sir. I didn't detect any music or audio playing through your speakers."

    wav_bytes = _to_wav_bytes(audio_array, sr)

    prompt = (
        "You are JARVIS's desktop audio perception engine. "
        "The following audio was recorded directly from the user's computer speakers or room.\n"
        f"User question: {query}\n"
        "Instructions: "
        "- If it is a music track or song (even instrumental or covered), identify the song title, artist, and genre.\n"
        "- If it is speech, a video, or podcast, summarize what is being said.\n"
        "- Keep your answer concise (1-2 sentences), direct, and natural for a spoken reply."
    )

    try:
        part = types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav")
        answer = gemini.text([part, prompt], tier=gemini.FAST)
        if not answer:
            return "I captured the audio stream, sir, but was unable to identify the track or speech."

        cleaned = answer.strip()
        if player:
            player.write_log("JARVIS", f"Audio Identification: {cleaned}")
        return cleaned
    except Exception as e:
        print(f"[AudioListener] Identification error: {e}")
        return "I captured the audio stream, sir, but encountered an error processing it with the neural network."


TOOL = {
    "name": "identify_system_audio",
    "description": (
        "Listen to what is currently playing through the user's speakers or headphones "
        "(videos, music, songs, streams, games) and identify the song, artist, or summarize the audio."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "Specific question or request (e.g., 'What song is this?', 'Summarize this video', 'What are they saying?')."
            },
            "seconds": {
                "type": "INTEGER",
                "description": "Duration to listen in seconds (default 5, min 3, max 10)."
            }
        }
    },
    "handler": run,
}
