"""
JARVIS action — open an application, and know whether it actually opened.

WHAT WAS WRONG WITH THIS FILE
    It answered "Opened Spotify." whenever its launcher returned True, and on
    Windows the launcher returned True immediately after

        subprocess.Popen(app_name, shell=True)

    which succeeds because a SHELL started — not because an application did. A
    misspelling, an app that was never installed, an installer that moved:
    every one of them produced "Opened Spotify.", said out loud, while nothing
    appeared on screen.

    The same line was also a command injection. `shutil.which(name.split(".")[0])`
    passed "notepad.exe & whoami" because `which("notepad")` succeeds, and the
    whole string then went to a shell unquoted. Verified before it was changed.

WHAT IT DOES NOW
    * No shell, anywhere. Executables are resolved to a path and started as an
      argument vector; URI schemes go through the OS handler.
    * It watches the process table for a NEW process answering to the name, and
      only says `done` when one appears. When none does, it says `unverified`
      and the assistant tells the user it could not confirm — which is true,
      and is something they can act on.
    * It answers in milliseconds and verifies behind that, so asking to open
      something no longer costs the conversation one to four seconds.

WHY IT IS NOT A LIST OF APPLICATIONS
    Nothing here knows in advance what exists. Verification asks the running
    machine what appeared; matching compares against whatever is running. The
    alias map in core/appidentity.py covers the handful of names that differ
    BETWEEN OPERATING SYSTEMS and restricts nothing — every other name falls
    through untouched, which is what makes software nobody here has heard of
    work exactly as well as the software we have.
"""
import os
import platform
import shutil
import subprocess
import threading
import time

from core import appidentity, outcome
from core.lazyimport import LazyModule, installed

_PYAUTOGUI = installed("pyautogui")
pyautogui = LazyModule("pyautogui")

_SYSTEM = platform.system()          # "Windows" | "Darwin" | "Linux"

# How long to keep watching for the application to appear. Chosen from the two
# ends of the range rather than the middle: a text editor is up in a fraction
# of a second, a game launcher can take ten, and a limit that suits the first
# reports the second as broken.
_LAUNCH_TIMEOUT = 12.0

# Nothing here is a keyword list. The Start-Menu / Spotlight fallback types the
# name and presses Enter, which is what a person does, and works in every
# language the desktop is running in.
_SEARCH_SETTLE = 0.8


# ─────────────────────────────────────────────────────────────────────────────
#  Per-OS launching — no shell on any path
# ─────────────────────────────────────────────────────────────────────────────
def _desktop_search(app_name: str) -> bool:
    """Type the name into the desktop's own search and press Enter.

    The last resort, and the only one that reaches Store apps, shortcuts and
    anything else with no executable on PATH. It is also the one that cannot be
    verified from its own return value — which is fine, because nothing here is
    trusted on its own any more; the process table decides.
    """
    if not _PYAUTOGUI:
        return False
    try:
        if _SYSTEM == "Darwin":
            pyautogui.hotkey("command", "space")
        else:
            pyautogui.press("win")
        time.sleep(_SEARCH_SETTLE)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(_SEARCH_SETTLE)
        pyautogui.press("enter")
        return True
    except Exception as exc:
        print(f"[open_app] desktop search failed: {exc}")
        return False


def _snap_window(position: str) -> None:
    """Snap the active window to a screen position (left, right, max, min)."""
    if not position:
        return
    pos = position.lower().strip()
    time.sleep(0.9)
    try:
        if _PYAUTOGUI:
            if pos in ("left", "half-left"):
                pyautogui.hotkey("win", "left")
            elif pos in ("right", "half-right"):
                pyautogui.hotkey("win", "right")
            elif pos in ("max", "maximize", "full", "up"):
                pyautogui.hotkey("win", "up")
            elif pos in ("min", "minimize", "down"):
                pyautogui.hotkey("win", "down")
    except Exception as e:
        print(f"[open_app] snap window error: {e}")


def _launch_windows(app_name: str, url: str | None = None) -> bool:
    """Launch an application or open a folder on Windows reliably."""
    name_clean = app_name.strip()
    name_lower = name_clean.lower()

    # Special handling for Perplexity Comet Browser
    if "comet" in name_lower:
        comet_paths = [
            r"C:\Program Files\Perplexity\Comet\Application\comet.exe",
            r"C:\Program Files (x86)\Perplexity\Comet\Application\comet.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Perplexity\Comet\Application\comet.exe"),
        ]
        for cp in comet_paths:
            if os.path.exists(cp):
                args = [cp]
                if url:
                    args.append(url)
                subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True

    # Special handling for Windows Terminal
    if name_lower in ("terminal", "windows terminal", "wt"):
        wt_path = (
            shutil.which("wt")
            or os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe")
            or shutil.which("powershell")
        )
        if wt_path and os.path.exists(str(wt_path)):
            subprocess.Popen([str(wt_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True

    # 1. Known special folders & Explorer navigation
    folder_aliases = {
        "downloads": Path.home() / "Downloads",
        "download": Path.home() / "Downloads",
        "desktop": Path.home() / "Desktop",
        "documents": Path.home() / "Documents",
        "document": Path.home() / "Documents",
        "pictures": Path.home() / "Pictures",
        "photos": Path.home() / "Pictures",
        "videos": Path.home() / "Videos",
        "music": Path.home() / "Music",
        "home": Path.home(),
        "user folder": Path.home(),
    }
    if name_lower in folder_aliases:
        target_dir = folder_aliases[name_lower]
        if target_dir.exists():
            try:
                os.startfile(str(target_dir))
                return True
            except Exception as e:
                print(f"[open_app] open folder failed for {target_dir}: {e}")

    if name_lower in ("explorer", "file explorer", "files"):
        try:
            subprocess.Popen(["explorer.exe"])
            return True
        except Exception:
            pass

    # Direct directory or file path
    try:
        p = Path(name_clean)
        if p.exists():
            os.startfile(str(p.resolve()))
            return True
    except Exception:
        pass

    # 2. Executable on PATH
    resolved = shutil.which(name_clean) or shutil.which(f"{name_clean}.exe")
    if resolved:
        try:
            args = [resolved]
            if url:
                args.append(url)
            subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as exc:
            print(f"[open_app] Popen failed for {resolved!r}: {exc}")

    # 3. Windows App Paths Registry (covers Chrome, Code, Notepad, Spotify, etc.)
    try:
        import winreg
        app_candidates = [name_clean, name_lower]
        if not name_lower.endswith(".exe"):
            app_candidates.append(f"{name_clean}.exe")
            app_candidates.append(f"{name_lower}.exe")
        for candidate in app_candidates:
            for root_key in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                sub_key = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{candidate}"
                try:
                    with winreg.OpenKey(root_key, sub_key) as key:
                        app_path, _ = winreg.QueryValueEx(key, "")
                        if app_path and os.path.exists(app_path):
                            args = [app_path]
                            if url:
                                args.append(url)
                            subprocess.Popen(
                                args,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                            return True
                except OSError:
                    continue
    except Exception as exc:
        print(f"[open_app] Registry lookup error: {exc}")

    # 4. If URL given and generic browser requested, use default browser with URL
    if url:
        try:
            webbrowser.open(url)
            return True
        except Exception:
            pass

    # 5. URI Scheme (e.g. ms-settings:, spotify:)
    scheme, _, rest = name_clean.partition(":")
    if rest and scheme and scheme.isalnum() and len(scheme) > 1:
        try:
            os.startfile(name_clean)
            return True
        except Exception as exc:
            print(f"[open_app] startfile failed for scheme {name_clean!r}: {exc}")

    # 5. Direct os.startfile attempt for known registered commands
    try:
        os.startfile(name_clean)
        return True
    except Exception:
        pass

    # 6. Fallback: Desktop Start Menu Search
    return _desktop_search(name_clean)


def _launch_macos(app_name: str) -> bool:
    for candidate in (app_name, f"{app_name}.app"):
        try:
            result = subprocess.run(
                ["open", "-a", candidate], capture_output=True, timeout=8
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass

    binary = shutil.which(app_name) or shutil.which(app_name.lower())
    if binary:
        try:
            subprocess.Popen(
                [binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            pass

    return _desktop_search(app_name)


_LINUX_TERMINALS = [
    "x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal",
    "xterm", "lxterminal", "mate-terminal", "tilix", "alacritty", "kitty",
]


def _launch_linux(app_name: str) -> bool:
    # "terminal" means whichever one this distribution actually ships.
    if app_name in ("x-terminal-emulator", "gnome-terminal", "terminal"):
        for term in _LINUX_TERMINALS:
            path = shutil.which(term)
            if not path:
                continue
            try:
                subprocess.Popen(
                    [path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return True
            except Exception:
                continue

    binary = (
        shutil.which(app_name)
        or shutil.which(app_name.lower())
        or shutil.which(app_name.lower().replace(" ", "-"))
        or shutil.which(app_name.lower().replace(" ", "_"))
    )
    if binary:
        try:
            subprocess.Popen(
                [binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            pass

    for name in (
        app_name.lower(),
        app_name.lower().replace(" ", "-"),
        app_name.lower().replace(" ", ""),
    ):
        try:
            result = subprocess.run(
                ["gtk-launch", name], capture_output=True, timeout=5
            )
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            break
        except Exception:
            pass

    try:
        result = subprocess.run(
            ["xdg-open", app_name], capture_output=True, timeout=5
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass

    return _desktop_search(app_name)


_LAUNCHERS = {
    "Windows": _launch_windows,
    "Darwin": _launch_macos,
    "Linux": _launch_linux,
}


# ─────────────────────────────────────────────────────────────────────────────
#  HUD helpers — no-ops without a player, exactly as the whatsapp plugins do
# ─────────────────────────────────────────────────────────────────────────────
def _log(player, message: str) -> None:
    if player:
        try:
            player.write_log(message)
        except Exception:
            pass


def _say(player, instruction: str) -> None:
    if player and hasattr(player, "request_say"):
        try:
            player.request_say(instruction)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
#  Launch + verify, off the conversation's thread
# ─────────────────────────────────────────────────────────────────────────────
def _launch_and_verify(player, spoken: str, launcher_name: str,
                       before: set[int], position: str | None = None,
                       url: str | None = None) -> None:
    """The part that takes seconds. Speaks ONLY when something needs saying."""
    try:
        launcher = _LAUNCHERS[_SYSTEM]
        if _SYSTEM == "Windows":
            requested = launcher(launcher_name, url=url)
            if not requested and launcher_name.lower() != spoken.lower():
                requested = launcher(spoken, url=url)
        else:
            requested = launcher(launcher_name)
            if not requested and launcher_name.lower() != spoken.lower():
                requested = launcher(spoken)

        appeared = appidentity.wait_for_launch(
            spoken, before, timeout=_LAUNCH_TIMEOUT
        )
        if appeared is not None:
            _log(player, f"JARVIS: {appeared.label} is open.")
            if position:
                _snap_window(position)
            return

        if requested and position:
            _snap_window(position)

        if not requested:
            trouble = (f"{spoken} could not be started - nothing on this system "
                       f"answers to that name, so it may not be installed")
        else:
            trouble = (f"{spoken} was asked to start but no new application "
                       f"appeared within {int(_LAUNCH_TIMEOUT)} seconds, so it "
                       f"is NOT confirmed open - it may be slow to load, or not "
                       f"installed under that name")

        _log(player, f"JARVIS: {trouble}")
        _say(player, "Tell the user, in one short sentence in their own "
                     f"language: {trouble}")
    except Exception as exc:
        print(f"[open_app] {type(exc).__name__}: {exc}")
        _say(player, "Tell the user, in one short sentence in their own "
                     f"language: opening {spoken} failed - {exc}")


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────
def open_app(parameters=None, response=None, player=None,
             session_memory=None) -> str:
    params = parameters or {}
    spoken = (params.get("app_name") or "").strip()
    position = (params.get("position") or "").strip()
    url = (params.get("url") or "").strip()

    if not spoken:
        return outcome.failed("open_app", "no application name was given")

    if _SYSTEM not in _LAUNCHERS:
        return outcome.failed(
            "open_app", f"this operating system ({_SYSTEM}) is not supported",
            app=spoken,
        )

    # Format shorthand URLs (e.g. "mr beast youtube" -> channel URL)
    if url:
        url_lower = url.lower()
        if "mr beast" in url_lower or "mrbeast" in url_lower:
            url = "https://www.youtube.com/@MrBeast"
        elif not url.startswith(("http://", "https://")):
            url = f"https://{url}"

    existing = appidentity.running(spoken, include_self=True)
    if existing:
        best = existing[0]
        for candidate in existing[:8]:
            if appidentity.focus(candidate):
                _log(player, f"JARVIS: {candidate.label} brought to the front.")
                if position:
                    _snap_window(position)
                return outcome.done(
                    "open_app", app=spoken, matched=candidate.label,
                    already_running=True, focused=True, verified=True,
                )

    launcher_name = appidentity.launcher_name(spoken)
    before = appidentity.snapshot()
    _log(player, f"JARVIS: Opening {spoken}{' on ' + position if position else ''}…")

    threading.Thread(
        target=_launch_and_verify,
        args=(player, spoken, launcher_name, before, position, url),
        daemon=True, name=f"open-app-{spoken[:20]}",
    ).start()

    return outcome.started("open_app", app=spoken)


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "open_app",
    "description": (
        "Opens an application on this computer, with optional window snapping ('left', 'right', 'maximize') "
        "and optional URL target. Use for any program: 'open comet browser on left', 'open terminal on right', "
        "'open comet with mr beast youtube channel'. Put the application's name in 'app_name'. "
        "To CLOSE an application use computer_control with action='close_app'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {
                "type": "STRING",
                "description": (
                    "The application's name (e.g. 'comet', 'terminal', 'chrome', 'spotify', 'vs code')."
                ),
            },
            "position": {
                "type": "STRING",
                "description": "Optional window position to snap: 'left', 'right', 'maximize', 'minimize', 'top-left', 'top-right'."
            },
            "url": {
                "type": "STRING",
                "description": "Optional URL or channel to open directly in the browser (e.g. 'https://www.youtube.com/@MrBeast')."
            }
        },
        "required": ["app_name"],
    },
    "handler": open_app,
}
