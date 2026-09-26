@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\ollama_local.ps1" -Action Start -DataRoot "%LOCALAPPDATA%\RecurGO"
set "result=%errorlevel%"
echo.
pause
exit /b %result%
