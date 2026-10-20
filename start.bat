@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=paradigme_venv\Scripts\python.exe"
if exist "%PYTHON%" goto ready
where python >nul 2>nul
if errorlevel 1 (
  echo Install Python 3.10 or newer, then run this script again.
  exit /b 1
)
python -c "import sys; sys.exit(sys.version_info < (3,10))"
if errorlevel 1 exit /b 1
python -m venv paradigme_venv
if errorlevel 1 exit /b 1
:ready
"%PYTHON%" -c "import fastapi,uvicorn,httpx,reportlab,PIL"
if errorlevel 1 (
  "%PYTHON%" -m pip install -r requirements.txt
  if errorlevel 1 exit /b 1
)
if not exist config.json copy /y config.example.json config.json >nul
if /i "%~1"=="--install" exit /b 0
echo Open http://127.0.0.1:8765 unless you changed the configured port.
echo Stop Paradigme with Ctrl+C in this window.
"%PYTHON%" "%~dp0app.py"
exit /b %errorlevel%
