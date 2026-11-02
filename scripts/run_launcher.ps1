# Run Git updates outside run.bat so an updated batch file is read from the start.
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
$log = $null
$result = 1

function Write-LaunchLine {
    param([string]$Line, [ConsoleColor]$Color)
    if ($PSBoundParameters.ContainsKey('Color')) {
        Write-Host $Line -ForegroundColor $Color
    } else {
        Write-Host $Line
    }
    if ($null -ne $script:log) {
        $script:log.WriteLine($Line)
    }
}

function Show-StartupSplash {
    $border = '  +' + ('=' * 70) + '+'
    $art = @(
        ' GGGG  UU  UU RRRRR  UU  UU MM   MM  OOOO     JJJJ IIIIII',
        'GG     UU  UU RR  RR UU  UU MMM MMM OO  OO      JJ   II',
        'GG GGG UU  UU RRRRR  UU  UU MM M MM OO  OO      JJ   II',
        'GG  GG UU  UU RR RR  UU  UU MM   MM OO  OO JJ   JJ   II',
        ' GGGG   UUUU  RR  RR  UUUU  MM   MM  OOOO   JJJJ  IIIIII'
    )
    $artWidth = ($art | Measure-Object -Property Length -Maximum).Maximum
    $art = @($art | ForEach-Object { $_.PadRight($artWidth) })
    Write-LaunchLine ''
    Write-LaunchLine $border -Color DarkCyan
    $rows = @('', '*  G U R U M O J I  *', '') + $art + @('', '---  MADE BY Re.kloc  ---', '')
    foreach ($row in $rows) {
        $padding = [int][Math]::Floor((70 - $row.Length) / 2)
        $line = '  |' + ((' ' * $padding) + $row).PadRight(70) + '|'
        $color = if ($row -like '*Re.kloc*') { 'Yellow' } else { 'Cyan' }
        Write-LaunchLine $line -Color $color
    }
    Write-LaunchLine $border -Color DarkCyan
    Write-LaunchLine ''
    Start-Sleep -Milliseconds 600
}

function Invoke-LaunchGit {
    param([string[]]$GitArguments)
    $lines = @(& git @GitArguments 2>&1)
    $code = $LASTEXITCODE
    return [pscustomobject]@{
        Code = $code
        Lines = @($lines | ForEach-Object { $_.ToString() })
    }
}

function Write-ReleaseInfo {
    # Read the version without importing the app or requiring Python packages.
    $appPath = Join-Path $ProjectRoot 'src\gurumoji\app.py'
    $version = 'Unknown'
    $updated = 'Unknown'
    if (Test-Path -LiteralPath $appPath) {
        $source = Get-Content -LiteralPath $appPath -Raw -Encoding UTF8
        if ($source -match '(?m)^APP_VERSION\s*=\s*["'']([^"'']+)["'']') {
            $version = $Matches[1]
        }
        $appFile = Get-Item -LiteralPath $appPath
        $updated = $appFile.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss zzz') + ' (app.py file)'
    }
    if ((Test-Path -LiteralPath (Join-Path $ProjectRoot '.git')) -and
        (Get-Command git -ErrorAction SilentlyContinue)) {
        $commit = Invoke-LaunchGit -GitArguments @('log', '-1', '--format=%cI', 'HEAD', '--')
        if ($commit.Code -eq 0 -and $commit.Lines) {
            $updated = ([DateTimeOffset]::Parse($commit.Lines[0])).ToLocalTime().ToString('yyyy-MM-dd HH:mm:ss zzz') + ' (Git commit)'
        }
    }
    Write-LaunchLine "  VERSION      : $version" -Color Yellow
    Write-LaunchLine "  LAST UPDATED : $updated" -Color Cyan
    Write-LaunchLine ('  ' + ('=' * 72)) -Color DarkCyan
    Write-LaunchLine ''
}

function Update-Source {
    if ($env:MOJIOKOSI_SKIP_UPDATE_CHECK -eq '1') { return }
    Write-LaunchLine 'Checking Git for updates ...'
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-LaunchLine 'Git was not found. Starting the installed version.'
        return
    }
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot '.git'))) {
        Write-LaunchLine 'This folder is not a Git checkout. Starting the installed version.'
        return
    }
    $branch = Invoke-LaunchGit -GitArguments @('branch', '--show-current')
    if ($branch.Code -ne 0 -or -not $branch.Lines) {
        Write-LaunchLine 'No current branch (detached HEAD). Starting the installed version.'
        return
    }
    $branchName = $branch.Lines[0]
    $remote = Invoke-LaunchGit -GitArguments @('config', '--get', "branch.$branchName.remote")
    $remoteName = 'origin'
    if ($remote.Code -eq 0 -and $remote.Lines) { $remoteName = $remote.Lines[0] }
    if ($remoteName -eq '.') {
        Write-LaunchLine 'The upstream is a local branch. Starting the installed version.'
        return
    }
    $fetch = Invoke-LaunchGit -GitArguments @('fetch', '--prune', $remoteName)
    $fetch.Lines | ForEach-Object { Write-LaunchLine $_ }
    if ($fetch.Code -ne 0) {
        Write-LaunchLine 'Source update check failed. Starting the installed version.'
        return
    }
    $upstream = Invoke-LaunchGit -GitArguments @('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}')
    $target = "$remoteName/$branchName"
    if ($upstream.Code -eq 0 -and $upstream.Lines) { $target = $upstream.Lines[0] }
    $count = Invoke-LaunchGit -GitArguments @('rev-list', '--count', "HEAD..$target", '--')
    if ($count.Code -ne 0) {
        Write-LaunchLine 'No matching remote branch was found. Starting the installed version.'
        return
    }
    if ($count.Lines[0] -eq '0') {
        Write-LaunchLine 'Source code is up to date.'
        return
    }
    $status = Invoke-LaunchGit -GitArguments @('status', '--porcelain', '--untracked-files=all')
    if ($status.Code -ne 0 -or $status.Lines) {
        Write-LaunchLine 'A newer version is available, but local changes could not be ruled out.'
        Write-LaunchLine 'Automatic update was skipped to protect local files.'
        return
    }
    Write-LaunchLine "Updating source code from $target ..."
    # Merge the fetched target explicitly; this also works without upstream config.
    $merge = Invoke-LaunchGit -GitArguments @('merge', '--ff-only', '--no-edit', $target)
    $merge.Lines | ForEach-Object { Write-LaunchLine $_ }
    if ($merge.Code -ne 0) {
        Write-LaunchLine 'Automatic update failed (branches may have diverged). Starting the installed version.'
    } else {
        Write-LaunchLine 'Source code update completed. Starting the updated version.'
    }
}

try {
    $logDirectory = Join-Path $ProjectRoot 'runtime\logs'
    [System.IO.Directory]::CreateDirectory($logDirectory) | Out-Null
    $logPath = Join-Path $logDirectory ("startup-{0}-{1}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss-fff'), $PID)
    $log = [System.IO.StreamWriter]::new($logPath, $false, [System.Text.UTF8Encoding]::new($false))
    $log.AutoFlush = $true
    Show-StartupSplash
    Write-LaunchLine "Startup log: $logPath"
    Update-Source
    $visualizationShortcut = Join-Path $ProjectRoot 'scripts\ensure_visualization_shortcut.ps1'
    if (Test-Path -LiteralPath $visualizationShortcut) {
        try {
            & $visualizationShortcut | ForEach-Object { Write-LaunchLine $_ }
        } catch {
            Write-LaunchLine "Visualization Obsidian shortcut could not be created: $($_.Exception.Message)"
        }
    }
    # Show the version and commit timestamp of the code that will actually start.
    Write-ReleaseInfo

    $env:MOJIOKOSI_LAUNCH_WORKER = '1'
    $env:MOJIOKOSI_NO_PAUSE = '1'
    $env:MOJIOKOSI_SKIP_UPDATE_CHECK = '1'
    # Merge stderr in cmd so Python tracebacks are logged as plain text.
    # Use an explicit relative path: cmd skips the current directory when
    # NoDefaultCurrentDirectoryInExePath is set.
    & $env:ComSpec /d /c 'call .\run.bat 2>&1' | ForEach-Object { Write-LaunchLine $_ }
    $result = $LASTEXITCODE
    if ($result -ne 0) {
        Write-LaunchLine "Startup failed (exit code $result). See the error details above."
    }
    Write-LaunchLine "Startup log: $logPath"
} catch {
    Write-Host "Launcher failed: $($_.Exception.Message)"
    if ($null -ne $log) { $log.WriteLine($_.ToString()) }
    $result = 1
} finally {
    if ($null -ne $log) { $log.Dispose() }
}
exit $result
