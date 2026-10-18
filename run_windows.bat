@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo Python is not installed. Install it from https://www.python.org/downloads/
  echo IMPORTANT: check "Add Python to PATH" during installation.
  pause
  exit /b 1
)
echo [2/3] Installing libraries (first time only, 1-5 minutes)...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Install failed. Please copy the error above and send it to Claude.
  pause
  exit /b 1
)
echo [3/3] Starting the app. Open http://localhost:8501 in your browser.
echo To stop: close this window or press Ctrl+C.
python -m streamlit run app.py
pause
