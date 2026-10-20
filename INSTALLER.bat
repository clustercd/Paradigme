@echo off
setlocal
cd /d "%~dp0"
call start.bat --install
if errorlevel 1 exit /b 1
echo Installation ready. Run start.bat to launch Paradigme.
pause
