@echo off
rem Plays the browser version locally at http://localhost:8765 (close this window to stop it).
cd /d "%~dp0"
start "" "http://localhost:8765"
"C:\Users\new\boss\.venv\Scripts\python.exe" serve.py 8765
