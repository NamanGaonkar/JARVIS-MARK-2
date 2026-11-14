"""
actions/steam_launcher.py — Steam Voice Game Launcher for JARVIS

Automatically discovers all installed Steam games on the system and launches them
via the native Windows steam:// protocol.
"""
import glob
import os
import re
import winreg
from pathlib import Path

def _get_steam_path() -> Path | None:
    for root in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
        try:
            key = winreg.OpenKey(root, r"Software\Valve\Steam")
            path, _ = winreg.QueryValueEx(key, "SteamPath")
            if path and os.path.exists(path):
                return Path(path)
        except Exception:
            pass
    # Common default fallback
    default_p = Path(r"C:\Program Files (x86)\Steam")
    if default_p.exists():
        return default_p
    return None

def _get_all_library_folders(steam_path: Path) -> list[Path]:
    folders = [steam_path]
    vdf = steam_path / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        try:
            with open(vdf, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                # Matches "path" "\path\to\library"
                paths = re.findall(r'"path"\s+"([^"]+)"', content)
                for p in paths:
                    clean = Path(p.replace("\\\\", "\\"))
                    if clean.exists() and clean not in folders:
                        folders.append(clean)
        except Exception as e:
            print(f"[SteamLauncher] Error reading libraryfolders.vdf: {e}")
    return folders

def get_installed_steam_games() -> dict[str, str]:
    """Returns {app_id: game_name} for all installed Steam games."""
    steam_path = _get_steam_path()
    if not steam_path:
        return {}
    
    games = {}
    libraries = _get_all_library_folders(steam_path)
    for lib in libraries:
        steamapps = lib / "steamapps"
        if not steamapps.exists():
            continue
        manifests = glob.glob(str(steamapps / "appmanifest_*.acf"))
        for m in manifests:
            try:
                with open(m, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    name_m = re.search(r'"name"\s+"([^"]+)"', content)
                    appid_m = re.search(r'"appid"\s+"([^"]+)"', content)
                    if name_m and appid_m:
                        name = name_m.group(1).strip()
                        appid = appid_m.group(1).strip()
                        # Ignore common redistributables
                        if "Steamworks" not in name and "Common Redist" not in name:
                            games[appid] = name
            except Exception:
                pass
    return games

def steam_launcher(parameters: dict, player=None, session_memory=None) -> str:
    """Launch or list installed Steam games."""
    action = str(parameters.get("action", "launch")).lower().strip()
    target_name = str(parameters.get("game_name", "")).strip().lower()

    installed = get_installed_steam_games()
    if not installed:
        return "I could not locate any installed Steam games on this system, sir."

    if action in ("list", "list_games"):
        game_list = ", ".join(sorted(installed.values()))
        if player:
            player.write_log(f"STEAM: Installed games: {game_list}")
        return f"Installed Steam games: {game_list}."

    # Launch game
    if not target_name:
        return "Please specify the name of the Steam game you would like me to launch, sir."

    # Match game
    best_match = None
    for appid, title in installed.items():
        clean_title = title.lower()
        if target_name == clean_title or target_name in clean_title:
            best_match = (appid, title)
            break

    if not best_match:
        # Fuzzy match attempt
        import difflib
        titles = list(installed.values())
        matches = difflib.get_close_matches(target_name, titles, n=1, cutoff=0.5)
        if matches:
            matched_title = matches[0]
            for appid, title in installed.items():
                if title == matched_title:
                    best_match = (appid, title)
                    break

    if best_match:
        appid, title = best_match
        try:
            os.startfile(f"steam://run/{appid}")
            if player:
                player.write_log(f"STEAM: Launching {title} (AppID {appid})...")
            return f"Launching {title} on Steam now, sir."
        except Exception as e:
            return f"Failed to launch {title}: {e}"

    return f"I could not find '{target_name}' in your Steam library. Available games include: {', '.join(installed.values())}."

TOOL = {
    "name": "steam_launcher",
    "description": (
        "Launches or lists games in the user's Steam library (e.g. Marvel Rivals, Cyberpunk 2077). "
        "Use action='launch' with 'game_name', or action='list' to see all installed games."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["launch", "list"],
                "description": "Whether to launch a game or list installed games."
            },
            "game_name": {
                "type": "STRING",
                "description": "Name of the game to launch (e.g. 'Marvel Rivals')."
            }
        },
        "required": ["action"],
    },
    "handler": steam_launcher,
}
