"""
JARVIS MARK 2 — Standalone Executable Build Script
Uses PyInstaller to bundle the application into a distribution.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def build():
    print("==================================================")
    print("      JARVIS MARK 2 — EXECUTABLE PACKAGER         ")
    print("==================================================")

    # Verify PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("[!] PyInstaller is not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Ensure required data folders exist
    data_folders = [
        ("config", "config"),
        ("core", "core"),
        ("gui", "gui"),
        ("actions", "actions"),
        ("providers", "providers"),
        ("plugins", "plugins"),
        ("memory", "memory"),
        ("dashboard", "dashboard"),
    ]

    add_data_args = []
    sep = ";" if sys.platform.startswith("win") else ":"
    for src, dst in data_folders:
        src_path = BASE_DIR / src
        if src_path.exists():
            add_data_args.extend(["--add-data", f"{src_path}{sep}{dst}"])

    icon_path = BASE_DIR / "config" / "jarvis.ico"
    if not icon_path.exists():
        icon_path = BASE_DIR / "config" / "ironman.ico"
    icon_args = []
    if icon_path.exists():
        icon_args = ["--icon", str(icon_path)]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "JARVIS-Mark-II",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--clean",
        *icon_args,
        *add_data_args,
        "--hidden-import", "PyQt6",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "psutil",
        "--hidden-import", "PIL",
        "--hidden-import", "winreg" if sys.platform == "win32" else "posix",
        "main.py"
    ]

    print("[*] Running command:")
    print(" ".join(cmd))
    print("==================================================")

    res = subprocess.run(cmd)
    if res.returncode == 0:
        # Guarantee zero personal API key leakage into release distributions
        dist_config_keys = BASE_DIR / "dist" / "JARVIS-Mark-II" / "config" / "api_keys.json"
        if dist_config_keys.exists():
            dist_config_keys.unlink()
            print("[*] Security check: Removed private api_keys.json from dist bundle.")
        print("\n[+] Build successful! Output located in dist/JARVIS-Mark-II/")
    else:
        print(f"\n[-] Build failed with exit code {res.returncode}")
        sys.exit(res.returncode)

if __name__ == "__main__":
    build()
