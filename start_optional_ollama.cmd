@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing_python
".venv\Scripts\python.exe" "scripts\start_optional_ollama.py"
set "start_result=%errorlevel%"
echo.
if not "%start_result%"=="0" echo Ollama did not start. Exit code: %start_result%
pause
exit /b %start_result%
:missing_python
echo Missing project Python environment: .venv\Scripts\python.exe
echo See docs\SOURCE_SETUP.md, Python environment section.
pause
exit /b 2
