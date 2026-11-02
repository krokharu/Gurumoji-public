@echo off
setlocal EnableExtensions
cd /d "%~dp0"

where powershell >nul 2>nul || (
  echo SETUP_ERROR: POWERSHELL_UNAVAILABLE
  echo Windows PowerShell was not found. Copy this error and ask an AI for a Windows PowerShell 5.1 installation method approved for your PC.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_gui.ps1"
set "SETUP_RESULT=%ERRORLEVEL%"
if not "%SETUP_RESULT%"=="0" (
  echo.
  echo SETUP_ERROR: POWERSHELL_OR_POLICY
  echo The setup window could not be opened. See the message above.
  echo On a managed PC, PowerShell or unsigned local scripts may be blocked by company policy. Copy this error and ask an AI how to confirm that restriction without bypassing it.
  pause
)
endlocal & exit /b %SETUP_RESULT%
