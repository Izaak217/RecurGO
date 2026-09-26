@echo off
rem RecurGO v0.1.3: reuse an already healthy project service in either network mode.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$status = & '.\scripts\ollama_local.ps1' -Action Status; if ($status.ProjectServiceRunning -and $status.ApiStatus -eq 'ready') { Write-Output 'Project Ollama is already ready.' } else { & '.\scripts\ollama_local.ps1' -Action Start }"
if errorlevel 1 echo Ollama could not start. RecurGO will still open with its local rule explanations.
".venv\Scripts\python.exe" -m recurgo.app
