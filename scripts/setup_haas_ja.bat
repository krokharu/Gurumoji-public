@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
if "%GURUMOJI_HAAS_WSL_DISTRO%"=="" set "GURUMOJI_HAAS_WSL_DISTRO=Ubuntu-24.04"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_haas_ja.ps1" -Distribution "%GURUMOJI_HAAS_WSL_DISTRO%"
exit /b %errorlevel%
