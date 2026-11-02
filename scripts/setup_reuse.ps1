param([string]$Distribution = 'Ubuntu-24.04')
$ErrorActionPreference = 'Stop'
# WindowsのWhisper環境を変更せず、専用WSL環境へ導入する。
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskLinuxRoot = & wsl.exe --distribution $Distribution --exec wslpath -a -u $taskRoot
if ($LASTEXITCODE -ne 0) { throw 'WSL2のUbuntuを起動できません。' }
& wsl.exe --distribution $Distribution --exec bash "$($taskLinuxRoot.Trim())/scripts/setup_reuse.sh"
if ($LASTEXITCODE -ne 0) { throw 'RE-USEの導入に失敗しました。CUDA拡張・ビルド環境など上のエラーを確認してください。' }
