@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\open_visualization_obsidian.ps1"
set "OPEN_RESULT=%ERRORLEVEL%"
if not "%OPEN_RESULT%"=="0" (
  echo.
  echo 可視化用Obsidianを開けませんでした。上のエラーをAIへ相談できます。
  pause
)
endlocal & exit /b %OPEN_RESULT%
