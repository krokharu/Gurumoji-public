@echo off
setlocal EnableExtensions
set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

set "VENV_DIR=%CD%\.venv"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "S3PRL_REPO=%CD%\runtime\models\s3prl-v0.4.17"
set "S3PRL_BOOTSTRAP=%CD%\scripts\bootstrap_s3prl.py"
set "HF_CHECK=%CD%\scripts\check_huggingface_access.py"
set "EMOTION_REQUIREMENTS=%CD%\config\requirements-emotion.txt"
set "EMOTION_REQUIREMENTS_HASH="
if not exist "%EMOTION_REQUIREMENTS%" (
  echo requirements-emotion.txt was not found: %EMOTION_REQUIREMENTS%
  goto :error
)
for /f "skip=1 tokens=*" %%H in ('certutil -hashfile "%EMOTION_REQUIREMENTS%" SHA256 2^>nul') do (
  if not defined EMOTION_REQUIREMENTS_HASH set "EMOTION_REQUIREMENTS_HASH=%%H"
)
set "EMOTION_REQUIREMENTS_HASH=%EMOTION_REQUIREMENTS_HASH: =%"
if not defined EMOTION_REQUIREMENTS_HASH (
  echo Could not calculate the requirements-emotion.txt fingerprint.
  goto :error
)
set "EMOTION_SETUP_MARKER=%VENV_DIR%\.setup_emotion_s3prl0417_%EMOTION_REQUIREMENTS_HASH%"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "SETUP_RESULT=0"
set "HF_CHECK_RAN=0"

echo Checking the base application environment ...
set "MOJIOKOSI_CHECK_ONLY="
set "MOJIOKOSI_SETUP_ONLY=1"
set "MOJIOKOSI_NO_PAUSE=1"
call "%CD%\run.bat"
if errorlevel 1 goto :error

if not exist "%PYTHON%" goto :error

"%PYTHON%" -c "import sys; from pathlib import Path; p=Path(sys.argv[1]); assert (p/'s3prl/version.txt').read_text(encoding='utf-8').strip() == '0.4.17' and (p/'s3prl/run_downstream.py').is_file()" "%S3PRL_REPO%" >nul 2>nul
if not errorlevel 1 (
  echo S3PRL repository already exists: %S3PRL_REPO%
  goto :s3prl_ready
)

if not exist "%S3PRL_REPO%" (
  where git >nul 2>nul
  if not errorlevel 1 (
    echo Cloning S3PRL v0.4.17 into %S3PRL_REPO% ...
    git clone --branch v0.4.17 --depth 1 https://github.com/s3prl/s3prl.git "%S3PRL_REPO%"
  )
)

"%PYTHON%" -c "import sys; from pathlib import Path; p=Path(sys.argv[1]); assert (p/'s3prl/version.txt').read_text(encoding='utf-8').strip() == '0.4.17' and (p/'s3prl/run_downstream.py').is_file()" "%S3PRL_REPO%" >nul 2>nul
if not errorlevel 1 goto :s3prl_ready

echo Git is unavailable or cloning did not complete. Using the Python download fallback ...
"%PYTHON%" "%S3PRL_BOOTSTRAP%" "%S3PRL_REPO%" || goto :error

:s3prl_ready

echo Installing optional AIST emotion dependencies ...
if not exist "%EMOTION_SETUP_MARKER%" (
  "%PYTHON%" -m pip install --no-cache-dir -r "%EMOTION_REQUIREMENTS%" || goto :error
)

echo Verifying the S3PRL emotion runtime ...
set "PYTHONPATH=%S3PRL_REPO%;%PYTHONPATH%"
cd /d "%S3PRL_REPO%\s3prl"
"%PYTHON%" -W ignore -c "import s3prl, soundfile, tensorboardX, torch, torchaudio, yaml; assert 'soundfile' in torchaudio.list_audio_backends(), 'TorchAudio SoundFile backend is unavailable'; import s3prl.run_downstream" >nul 2>nul || (
  echo S3PRL runtime verification failed. Details:
  "%PYTHON%" -W ignore -c "import s3prl, soundfile, tensorboardX, torch, torchaudio, yaml; assert 'soundfile' in torchaudio.list_audio_backends(), 'TorchAudio SoundFile backend is unavailable'; import s3prl.run_downstream"
  goto :error
)
"%PYTHON%" -m pip check || goto :error
if not exist "%EMOTION_SETUP_MARKER%" type nul > "%EMOTION_SETUP_MARKER%" || goto :error
echo S3PRL 0.4.17 emotion runtime verified.

echo.
echo Checking all Hugging Face tokens and gated-model agreements ...
set "HF_CHECK_RAN=1"
"%PYTHON%" "%HF_CHECK%"
if errorlevel 1 (
  set "SETUP_RESULT=1"
  echo.
  echo Dependencies are ready, but one or more Hugging Face checks are NG.
  echo Open every NG URL above, accept its terms, and run this file again.
) else (
  echo.
  echo AIST emotion setup and every Hugging Face access check completed.
  echo Enable AIST emotion analysis in the Web UI when needed.
)
goto :finish

:error
set "SETUP_RESULT=1"
echo.
echo Could not set up optional AIST emotion analysis.
echo Check README.md and the error above.

:finish
echo.
if "%HF_CHECK_RAN%"=="1" (
  echo Review the three [OK]/[NG] group results above.
) else (
  echo Review the setup error above.
)
echo This window will remain open until you press a key.
pause
endlocal & exit /b %SETUP_RESULT%
