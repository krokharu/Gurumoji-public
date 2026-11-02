@echo off
setlocal EnableExtensions
set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"
set "VENV_DIR=%CD%\.venv"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo No project virtual environment was found:
  echo %VENV_DIR%
  goto :end
)

echo This will delete this project's virtual environment:
echo %VENV_DIR%
echo.
echo Output files and downloaded Whisper / Hugging Face models are not deleted.
set /p "CONFIRM=Type DELETE to continue: "
if /I not "%CONFIRM%"=="DELETE" (
  echo Cancelled.
  goto :end
)

rmdir /s /q "%VENV_DIR%"
if exist "%VENV_DIR%" (
  echo Could not remove the virtual environment. Close the application and try again.
) else (
  echo Virtual environment was removed.
)

:end
pause
endlocal
