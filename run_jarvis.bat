@echo off
title JARVIS MARK 2
echo ========================================================
echo               INITIALISING JARVIS MARK 2
echo ========================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py %*
) else (
    python main.py %*
)
pause
