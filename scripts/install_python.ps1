# Downloads a reviewed CPython installer from python.org and installs it per-user.
# It is called only after the setup window has received explicit user confirmation.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$version = '3.13.15'
$installerUrl = 'https://www.python.org/ftp/python/3.13.15/python-3.13.15-amd64.exe'
$expectedSha256 = 'edec09c4853aeae9ac36efb8c9f95b6b8e2fee65eee56d9767a8b7c69c574403'
$installerPath = Join-Path ([System.IO.Path]::GetTempPath()) "python-$version-amd64.exe"

function Get-InstallFailureCode {
    param([System.Management.Automation.ErrorRecord]$ErrorRecord)

    $message = $ErrorRecord.ToString()
    if ($message -match '(?i)checksum') { return 'INTEGRITY' }
    if ($message -match '(?i)signature') { return 'SIGNATURE' }
    if ($message -match '(?i)proxy|407') { return 'PROXY' }
    if ($message -match '(?i)403|forbidden|access denied|blocked|filter') { return 'NETWORK_FILTER' }
    if ($message -match '(?i)tls|ssl|certificate|secure channel') { return 'TLS' }
    if ($message -match '(?i)name resolution|could not resolve|host.*not.*found|timed out|network.*unreachable|connect') { return 'NETWORK' }
    if ($message -match '(?i)temporary directory|temp.*access|cannot create.*temp') { return 'TEMP' }
    if ($message -match '(?i)disk.*full|not enough space|insufficient.*space') { return 'DISK' }
    if ($message -match '(?i)used by another process|file.*locked|sharing violation') { return 'FILE_LOCK' }
    if ($message -match '(?i)defender|antivirus|malware|virus') { return 'SECURITY_SOFTWARE' }
    if ($message -match '(?i)applocker|application control|group policy|blocked by your administrator|not permitted') { return 'POLICY' }
    if ($message -match '(?i)unauthorized|access.*denied|permission') { return 'PERMISSION' }
    return 'INSTALLER'
}

try {
    # Windows PowerShell 5.1 may otherwise negotiate an older TLS version.
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Write-Host "Downloading Python $version (64 bit) from python.org ..."
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath

    $actualSha256 = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSha256 -ne $expectedSha256) {
        throw "Downloaded installer checksum did not match the published Python $version checksum."
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $installerPath
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
        throw 'The downloaded Python installer does not have a valid Python Software Foundation signature.'
    }

    Write-Host 'Verified Python installer signature and checksum. Installing for the current user ...'
    $process = Start-Process -FilePath $installerPath -ArgumentList @(
        '/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_launcher=1', 'Include_pip=1', 'Include_test=0', 'Shortcuts=0'
    ) -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Python installer failed with exit code $($process.ExitCode)."
    }
    Write-Host "Python $version was installed. Close and reopen the setup window so it can read the updated PATH."
} catch {
    $code = Get-InstallFailureCode $_
    Write-Host "GURUMOJI_SETUP_ERROR: $code"
    Write-Host "Python setup failed: $($_.Exception.Message)"
    exit 1
} finally {
    if (Test-Path -LiteralPath $installerPath) {
        Remove-Item -LiteralPath $installerPath -Force -ErrorAction SilentlyContinue
    }
}
