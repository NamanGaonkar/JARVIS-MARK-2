"""
core/discord_rpc.py — Discord Rich Presence (RPC) for JARVIS Mark II

Lightweight, native Windows IPC implementation using \\\\.\\pipe\\discord-ipc-0.
Requires zero external dependencies. Updates status dynamically with JARVIS's state.
"""
import json
import os
import struct
import threading
import time
import uuid

# Client ID for JARVIS Mark II Rich Presence
# (Public JARVIS application ID)
DEFAULT_CLIENT_ID = "1307055953942726286"

OP_HANDSHAKE = 0
OP_FRAME     = 1
OP_CLOSE     = 2

class DiscordRPC:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = DiscordRPC()
            return cls._instance

    def __init__(self, client_id: str = DEFAULT_CLIENT_ID):
        self.client_id = client_id
        self._pipe = None
        self._running = False
        self._connected = False
        self._start_time = int(time.time())
        self._current_state = "Systems Nominal · Core Online"
        self._current_details = "JARVIS Mark II"
        self._thread = None

    def start(self):
        """Start the background Discord presence updater."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="discord-rpc")
        self._thread.start()

    def set_state(self, state: str, details: str = "JARVIS Mark II"):
        """Update presence state (e.g. 'Listening...', 'Thinking...', 'Speaking')."""
        self._current_state = state
        self._current_details = details
        if self._connected:
            self._send_activity()

    def stop(self):
        self._running = False
        self._disconnect()

    def _get_pipe_path(self) -> str | None:
        for i in range(10):
            p = f"\\\\.\\pipe\\discord-ipc-{i}"
            if os.path.exists(p):
                return p
        return None

    def _connect(self) -> bool:
        pipe_path = self._get_pipe_path()
        if not pipe_path:
            return False
        try:
            # Open named pipe on Windows in binary r+ mode
            self._pipe = open(pipe_path, "r+b", buffering=0)
            # Send Handshake
            handshake = json.dumps({"v": 1, "client_id": self.client_id})
            self._send_raw(OP_HANDSHAKE, handshake)
            resp = self._recv_raw()
            if resp:
                self._connected = True
                self._send_activity()
                return True
        except Exception:
            self._disconnect()
        return False

    def _disconnect(self):
        self._connected = False
        if self._pipe:
            try:
                self._pipe.close()
            except Exception:
                pass
            self._pipe = None

    def _send_raw(self, op: int, payload: str):
        if not self._pipe:
            return
        data = payload.encode("utf-8")
        header = struct.pack("<II", op, len(data))
        self._pipe.write(header + data)

    def _recv_raw(self) -> dict | None:
        if not self._pipe:
            return None
        try:
            header = self._pipe.read(8)
            if len(header) < 8:
                return None
            op, length = struct.unpack("<II", header)
            payload = self._pipe.read(length)
            return json.loads(payload.decode("utf-8"))
        except Exception:
            return None

    def _send_activity(self):
        if not self._connected or not self._pipe:
            return
        try:
            act = {
                "cmd": "SET_ACTIVITY",
                "args": {
                    "pid": os.getpid(),
                    "activity": {
                        "details": self._current_details,
                        "state": self._current_state,
                        "timestamps": {"start": self._start_time},
                        "assets": {
                            "large_image": "jarvis_core",
                            "large_text": "JARVIS Mark II Autonomous System",
                            "small_image": "online",
                            "small_text": "Online"
                        }
                    }
                },
                "nonce": str(uuid.uuid4())
            }
            self._send_raw(OP_FRAME, json.dumps(act))
        except Exception:
            self._disconnect()

    def _run_loop(self):
        while self._running:
            if not self._connected:
                self._connect()
            else:
                # Keepalive / verify connection
                try:
                    self._send_activity()
                except Exception:
                    self._disconnect()
            time.sleep(15)
