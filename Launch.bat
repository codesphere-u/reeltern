@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -m reeltern.cli gui
) else (
  python -m reeltern.cli gui
)
pause
