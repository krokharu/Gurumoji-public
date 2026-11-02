@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

rem Keep this block together: Git may replace run.bat while the launcher runs.
if /I not "%MOJIOKOSI_LAUNCH_WORKER%"=="1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_launcher.ps1"
  set "RUN_RESULT=!ERRORLEVEL!"
  if not "!RUN_RESULT!"=="0" (
    echo.
    echo Startup failed. Review the error above and the startup log shown above.
    if /I not "%MOJIOKOSI_NO_PAUSE%"=="1" pause
  )
  exit /b !RUN_RESULT!
)

rem Keep the complete Python environment inside this project folder.
set "VENV_DIR=%CD%\.venv"
set "REQUIREMENTS_FILE=%CD%\config\requirements.txt"
set "REQUIREMENTS_HASH="
if not exist "%REQUIREMENTS_FILE%" (
  echo requirements.txt was not found: %REQUIREMENTS_FILE%
  goto :error
)
for /f "skip=1 tokens=*" %%H in ('certutil -hashfile "%REQUIREMENTS_FILE%" SHA256 2^>nul') do (
  if not defined REQUIREMENTS_HASH set "REQUIREMENTS_HASH=%%H"
)
set "REQUIREMENTS_HASH=%REQUIREMENTS_HASH: =%"
if not defined REQUIREMENTS_HASH (
  echo Could not calculate the requirements.txt fingerprint.
  goto :error
)
set "SETUP_MARKER=%VENV_DIR%\.setup_cuda128_torch280_%REQUIREMENTS_HASH%"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"
set "RUN_RESULT=0"

rem Prefer Python 3.12, but detect any supported 64-bit Python 3.10 through 3.13.
set "BASE_PYTHON="
for %%V in (3.12 3.13 3.11 3.10) do (
  if not defined BASE_PYTHON (
    py -%%V -c "import sys; assert (3, 10) <= sys.version_info[:2] < (3, 14) and sys.maxsize > 2**32" >nul 2>nul
    if not errorlevel 1 set "BASE_PYTHON=py -%%V"
  )
)
if not defined BASE_PYTHON (
  python -c "import sys; assert (3, 10) <= sys.version_info[:2] < (3, 14) and sys.maxsize > 2**32" >nul 2>nul
  if not errorlevel 1 set "BASE_PYTHON=python"
)
if not defined BASE_PYTHON (
  echo Supported 64-bit Python 3.10 through 3.13 was not found.
  goto :error
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo Creating virtual environment in %VENV_DIR% ...
  %BASE_PYTHON% -m venv "%VENV_DIR%" || goto :error
)

set "PYTHON=%VENV_DIR%\Scripts\python.exe"
"%PYTHON%" -c "import sys; assert (3, 10) <= sys.version_info[:2] < (3, 14) and sys.maxsize > 2**32" || (
  echo The existing .venv uses an unsupported Python. Run scripts\cleanup_env.bat and try again.
  goto :error
)
if not exist "%SETUP_MARKER%" (
  echo Installing packages into %VENV_DIR% ...
  "%PYTHON%" -m pip install --no-cache-dir torch==2.8.0+cu128 torchvision==0.23.0+cu128 torchaudio==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128 || goto :error
  "%PYTHON%" -m pip install --no-cache-dir -r "%REQUIREMENTS_FILE%" || goto :error
  "%PYTHON%" -m pip check || goto :error
) else if /I not "%MOJIOKOSI_SKIP_LIBRARY_UPDATE%"=="1" (
  echo Checking Python libraries for compatible updates ...
  "%PYTHON%" -m pip install --disable-pip-version-check --upgrade --upgrade-strategy only-if-needed -r "%REQUIREMENTS_FILE%"
  if errorlevel 1 echo Library update check failed. Continuing with the installed environment.
)

rem CTranslate2 can discover CUDA/cuDNN DLLs shipped in PyTorch's wheel.
set "PATH=%VENV_DIR%\Lib\site-packages\torch\lib;%PATH%"
"%PYTHON%" -c "import ctranslate2; assert ctranslate2.__version__ == '4.8.1'" >nul 2>nul || (
  echo Installing CTranslate2 4.8.1 ...
  "%PYTHON%" -m pip install --no-cache-dir --upgrade --force-reinstall --no-deps ctranslate2==4.8.1 || goto :error
)
"%PYTHON%" -c "import numpy, whisper; assert numpy.__version__ == '2.2.6'" >nul 2>nul || (
  echo Installing OpenAI Whisper compatibility packages ...
  "%PYTHON%" -m pip install --no-cache-dir --upgrade --force-reinstall --no-deps numpy==2.2.6 openai-whisper==20250625 || goto :error
)
"%PYTHON%" -c "import flask" >nul 2>nul || (
  echo Installing Web UI packages ...
  "%PYTHON%" -m pip install --no-cache-dir -r "%REQUIREMENTS_FILE%" || goto :error
)
echo Checking required Python package imports ...
"%PYTHON%" -c "import ctranslate2, flask, numpy, torch, torchaudio, torchvision, whisper, whisperx" || (
  echo One or more required Python packages cannot be imported. Run scripts\cleanup_env.bat and try again.
  goto :error
)
"%PYTHON%" -m pip check || goto :error
if not exist "%SETUP_MARKER%" type nul > "%SETUP_MARKER%" || goto :error

rem imageio-ffmpeg ships a Windows ffmpeg executable with the Python package.
rem Copy it to the venv Scripts folder under the conventional name so every
rem child process (including Whisper and the Web UI) can resolve "ffmpeg".
set "PROJECT_FFMPEG=%VENV_DIR%\Scripts\ffmpeg.exe"
if not exist "%PROJECT_FFMPEG%" (
  echo Installing project-local FFmpeg ...
  set "PACKAGED_FFMPEG="
  rem Do not use FOR /F command substitution here.  CMD misparses a quoted
  rem executable path in that context on some Windows installations.
  set "FFMPEG_PATH_FILE=%VENV_DIR%\.imageio-ffmpeg-path.txt"
  "%PYTHON%" -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" > "!FFMPEG_PATH_FILE!" || goto :error
  set /p "PACKAGED_FFMPEG=" < "!FFMPEG_PATH_FILE!"
  del /q "!FFMPEG_PATH_FILE!" >nul 2>nul
  if not defined PACKAGED_FFMPEG (
    echo Could not obtain the FFmpeg executable from imageio-ffmpeg.
    goto :error
  )
  if not exist "!PACKAGED_FFMPEG!" (
    echo The packaged FFmpeg executable was not found: !PACKAGED_FFMPEG!
    goto :error
  )
  copy /y "!PACKAGED_FFMPEG!" "%PROJECT_FFMPEG%" >nul || goto :error
)
set "PATH=%VENV_DIR%\Scripts;%VENV_DIR%\Lib\site-packages\torch\lib;%PATH%"
where ffmpeg >nul 2>nul || (
  echo Project-local FFmpeg could not be added to PATH.
  goto :error
)
"%PYTHON%" -c "import torch; print('Torch:', torch.__version__); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'not available (CPU mode can be used)'); print('CUDA:', torch.version.cuda)" || goto :error
if /I "%MOJIOKOSI_CHECK_ONLY%"=="1" (
  echo Environment checks passed.
  goto :end
)
if /I "%MOJIOKOSI_SETUP_ONLY%"=="1" (
  echo Environment setup completed.
  goto :end
)
echo Starting Web UI at http://127.0.0.1:7860 ...
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
"%PYTHON%" -u -m gurumoji.app || goto :error
goto :end

:error
set "RUN_RESULT=%ERRORLEVEL%"
if "%RUN_RESULT%"=="0" set "RUN_RESULT=1"
echo.
echo Could not start the application. Please read README.md.
if /I not "%MOJIOKOSI_NO_PAUSE%"=="1" pause
:end
endlocal & exit /b %RUN_RESULT%
