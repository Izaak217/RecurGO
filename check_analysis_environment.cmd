@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing_python
if not exist "scripts\check_analysis_environment.py" goto missing_checker
".venv\Scripts\python.exe" "scripts\check_analysis_environment.py" --configure
set "check_result=%errorlevel%"
echo.
if "%check_result%"=="0" (
  echo KataGo analysis environment check passed.
) else (
  echo KataGo analysis environment check failed. Exit code: %check_result%
)
pause
exit /b %check_result%
:missing_python
echo Missing project Python environment: .venv\Scripts\python.exe
echo See docs\SOURCE_SETUP.md, Python environment section, then rerun this checker.
pause
exit /b 2
:missing_checker
echo Missing checker script: scripts\check_analysis_environment.py
echo Restore the complete project files and retry.
pause
exit /b 2
