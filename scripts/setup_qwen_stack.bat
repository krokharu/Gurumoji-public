@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
del /q ".venv-qwen\.qwen-stack-ready" ".venv-nemotron\.qwen-stack-ready" 2>nul

where py >nul 2>nul || goto :no_python
py -3.12 -c "import sys; assert sys.version_info[:2] == (3, 12)" >nul 2>nul || goto :no_python

set "QWEN_PYTHON=%CD%\.venv-qwen\Scripts\python.exe"
if not exist "%QWEN_PYTHON%" (
  py -3.12 -m venv "%CD%\.venv-qwen" || goto :error
)
"%QWEN_PYTHON%" -m pip install --upgrade pip || goto :error
"%QWEN_PYTHON%" -m pip install torch==2.8.0+cu128 torchaudio==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128 || goto :error
"%QWEN_PYTHON%" -m pip install qwen-asr==0.0.6 || goto :error
"%QWEN_PYTHON%" -m pip check || goto :error

set "NEMOTRON_PYTHON=%CD%\.venv-nemotron\Scripts\python.exe"
if not exist "%NEMOTRON_PYTHON%" (
  py -3.12 -m venv "%CD%\.venv-nemotron" || goto :error
)
"%NEMOTRON_PYTHON%" -m pip install --upgrade pip || goto :error
"%NEMOTRON_PYTHON%" -m pip install torch==2.8.0+cu128 torchaudio==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128 || goto :error
"%NEMOTRON_PYTHON%" -m pip install "git+https://github.com/huggingface/transformers.git" accelerate soundfile || goto :error
"%NEMOTRON_PYTHON%" -m pip check || goto :error
>".venv-qwen\.qwen-stack-ready" echo ready
>".venv-nemotron\.qwen-stack-ready" echo ready

echo.
echo Qwen3-ASR, Qwen3-ForcedAligner, and Nemotron 3 runtimes are ready.
echo Model weights will download from Hugging Face the first time the Qwen stack runs.
exit /b 0

:no_python
echo Python 3.12 is required for the isolated Qwen/Nemotron runtimes.
exit /b 1

:error
echo Setup failed. The existing WhisperX environment was not modified.
exit /b 1
