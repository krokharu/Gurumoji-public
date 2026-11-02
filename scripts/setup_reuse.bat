@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_reuse.ps1" %*
if errorlevel 1 exit /b 1
