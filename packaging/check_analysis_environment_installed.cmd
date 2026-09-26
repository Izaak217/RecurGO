@echo off
setlocal
cd /d "%~dp0"
if not exist "%SystemRoot%\System32\msvcp140.dll" goto missing_vc
if not exist "%SystemRoot%\System32\vcruntime140.dll" goto missing_vc
if not exist "%SystemRoot%\System32\vcruntime140_1.dll" goto missing_vc
"%~dp0RecurGO-Environment-Check.exe" --configure
set "result=%errorlevel%"
echo.
pause
exit /b %result%

:missing_vc
echo KataGo requires the Microsoft Visual C++ Redistributable x64.
echo https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist
start "" "https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist"
echo.
pause
exit /b 2
