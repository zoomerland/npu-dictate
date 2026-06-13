@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
".venv\Scripts\pythonw.exe" ".\tools\voice_dictation_app.py"
