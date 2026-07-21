@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python ne nayden. Ustanovite Python 3.11 ili novee: https://python.org/downloads/
  pause
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo Sozdayu virtualnoe okruzhenie...
  py -3 -m venv .venv
)

echo Ustanavlivayu zavisimosti...
.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 (
  echo Ne udalos ustanovit zavisimosti.
  pause
  exit /b 1
)

echo GEOtochka zapushchena: http://127.0.0.1:8000
start "" http://127.0.0.1:8000
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
