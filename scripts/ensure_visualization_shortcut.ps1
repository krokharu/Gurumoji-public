# Create or refresh a root-level shortcut only when Obsidian is installed.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Find-ObsidianExecutable {
    $command = Get-Command obsidian -CommandType Application -ErrorAction SilentlyContinue
    if ($command -and (Test-Path -LiteralPath $command.Source)) { return $command.Source }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Obsidian\Obsidian.exe'),
        (Join-Path ${env:ProgramFiles} 'Obsidian\Obsidian.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Obsidian\Obsidian.exe')
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
    }
    return $null
}

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $root 'open_visualization_obsidian.bat'
$shortcutPath = Join-Path $root '可視化用Obsidianを開く.lnk'
$obsidian = Find-ObsidianExecutable
if (-not $obsidian) {
    Write-Output 'Obsidian was not detected; visualization shortcut was not created.'
    exit 0
}
if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Visualization launcher was not found: $launcher"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $env:ComSpec
$shortcut.Arguments = ('/d /c ""{0}""' -f $launcher)
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = "$obsidian,0"
$shortcut.WindowStyle = 7
$shortcut.Description = 'Gurumoji の可視化用 Obsidian Vault を開く'
$shortcut.Save()
Write-Output "Visualization Obsidian shortcut is ready: $shortcutPath"
