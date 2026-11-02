param([string]$Distribution = "Ubuntu-24.04")
$ErrorActionPreference = 'Stop'
# 導入先とモデルは専用環境に限定し、アプリのPythonを変更しない。
$repoRoot = Split-Path -Parent $PSScriptRoot
$linuxRoot = & wsl.exe --distribution $Distribution --exec wslpath -a -u $repoRoot
if ($LASTEXITCODE -ne 0) { throw 'WSL2のUbuntuを起動できません。' }
& wsl.exe --distribution $Distribution --exec bash "$($linuxRoot.Trim())/scripts/setup_haas_ja.sh"
if ($LASTEXITCODE -ne 0) { throw 'Haas-jaの導入に失敗しました。上のエラーを確認してください。' }
