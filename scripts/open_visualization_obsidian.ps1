[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-ObsidianInstalled {
    $paths = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Obsidian\Obsidian.exe'),
        (Join-Path ${env:ProgramFiles} 'Obsidian\Obsidian.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Obsidian\Obsidian.exe')
    )
    if (Get-Command obsidian -CommandType Application -ErrorAction SilentlyContinue) { return $true }
    return [bool]($paths | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1)
}

try {
    if (-not (Test-ObsidianInstalled)) {
        throw 'Obsidian が見つかりません。Obsidianをインストールしてからもう一度実行してください。'
    }
    $root = Split-Path -Parent $PSScriptRoot
    $vault = Join-Path $root 'runtime\data\obsidian\VisualizationVault'
    [System.IO.Directory]::CreateDirectory($vault) | Out-Null
    $uri = 'obsidian://open?path=' + [Uri]::EscapeDataString($vault)
    Start-Process $uri
    Write-Host "可視化用Vaultを開きました: $vault"
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
