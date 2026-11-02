# Requires Windows PowerShell 5.1 or PowerShell 7 on Windows.
# This bootstrapper uses only built-in WinForms so it can run before Python exists.

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$script:Root = Split-Path -Parent $PSScriptRoot
$script:TokenFile = Join-Path $script:Root 'config\tokens.json'
$script:RunBatch = Join-Path $script:Root 'run.bat'
$script:PythonInstallerScript = Join-Path $PSScriptRoot 'install_python.ps1'
$script:VisualizationShortcutScript = Join-Path $PSScriptRoot 'ensure_visualization_shortcut.ps1'
$script:ActiveProcess = $null
$script:ActiveOutput = $null
$script:ActiveLines = $null
$script:ActiveTitle = ''

function Get-JsonSettings {
    $settings = [ordered]@{}
    if (-not (Test-Path -LiteralPath $script:TokenFile)) {
        return $settings
    }
    try {
        $raw = Get-Content -LiteralPath $script:TokenFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -eq $raw) { return $settings }
        foreach ($property in $raw.PSObject.Properties) {
            $settings[$property.Name] = $property.Value
        }
        return $settings
    } catch {
        throw "tokens.json を読み込めません: $($_.Exception.Message)"
    }
}

function Get-SettingText {
    param(
        [System.Collections.IDictionary]$Settings,
        [string]$Name,
        [string]$Fallback = ''
    )
    if ($Settings.Contains($Name) -and $null -ne $Settings[$Name]) {
        return [string]$Settings[$Name]
    }
    return $Fallback
}

function Set-SettingValue {
    param(
        [System.Collections.IDictionary]$Settings,
        [string]$Name,
        [string]$Value
    )
    $Settings[$Name] = $Value.Trim()
}

function Save-JsonSettings {
    param([System.Collections.IDictionary]$Settings)
    $directory = Split-Path -Parent $script:TokenFile
    $temporary = Join-Path $directory ('.tokens-{0}.tmp' -f [guid]::NewGuid().ToString('N'))
    try {
        $content = $Settings | ConvertTo-Json -Depth 20
        [System.IO.File]::WriteAllText(
            $temporary,
            $content + [Environment]::NewLine,
            [System.Text.UTF8Encoding]::new($false)
        )
        Move-Item -LiteralPath $temporary -Destination $script:TokenFile -Force
    } finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
        }
    }
}

function Find-SupportedPython {
    $versions = @('3.12', '3.13', '3.11', '3.10')
    $pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonLauncher) {
        foreach ($version in $versions) {
            $output = @(& $pythonLauncher.Source ("-$version") -c "import struct,sys; print('.'.join(map(str, sys.version_info[:3])) if struct.calcsize('P') == 8 else '')" 2>$null)
            if ($LASTEXITCODE -eq 0 -and $output -and $output[0].ToString().Trim()) {
                return "Python $($output[0].ToString().Trim()) (py -$version)"
            }
        }
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        $output = @(& $python.Source -c "import struct,sys; print('.'.join(map(str, sys.version_info[:3])) if (3, 10) <= sys.version_info[:2] < (3, 14) and struct.calcsize('P') == 8 else '')" 2>$null)
        if ($LASTEXITCODE -eq 0 -and $output -and $output[0].ToString().Trim()) {
            return "Python $($output[0].ToString().Trim()) (python)"
        }
    }
    return ''
}

function Get-EnvironmentReport {
    $python = Find-SupportedPython
    $venvPython = Join-Path $script:Root '.venv\Scripts\python.exe'
    $tokenState = if (Test-Path -LiteralPath $script:TokenFile) { '設定ファイルあり' } else { '未作成' }
    $lines = @(
        $(if ($python) { "Python: OK — $python" } else { 'Python: 未検出（3.10〜3.13 / 64 bit が必要）' }),
        'FFmpeg: アプリ環境の作成時にプロジェクト内へ自動導入',
        $(if (Test-Path -LiteralPath $venvPython) { "アプリ環境: OK — $venvPython" } else { 'アプリ環境: 未作成' }),
        "tokens.json: $tokenState"
    )
    return ($lines -join [Environment]::NewLine)
}

function Refresh-ProcessPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = @($machine, $user, $env:Path) -join ';'
}

function Get-SetupFailureGuidance {
    param(
        [string]$Title,
        [string[]]$Lines
    )
    $output = $Lines -join [Environment]::NewLine
    $code = ''
    if ($output -match 'GURUMOJI_SETUP_ERROR:\s*([A-Z_]+)') { $code = $Matches[1] }
    if (-not $code) {
        if ($output -match '(?i)proxy|407') { $code = 'PROXY' }
        elseif ($output -match '(?i)403|forbidden|blocked|web filter') { $code = 'NETWORK_FILTER' }
        elseif ($output -match '(?i)tls|ssl|certificate|secure channel') { $code = 'TLS' }
        elseif ($output -match '(?i)timed out|network.*unreachable|could not resolve|name resolution|connection') { $code = 'NETWORK' }
        elseif ($output -match '(?i)temporary directory|temp.*access|cannot create.*temp') { $code = 'TEMP' }
        elseif ($output -match '(?i)disk.*full|not enough space|insufficient.*space') { $code = 'DISK' }
        elseif ($output -match '(?i)used by another process|file.*locked|sharing violation') { $code = 'FILE_LOCK' }
        elseif ($output -match '(?i)defender|antivirus|malware|virus') { $code = 'SECURITY_SOFTWARE' }
        elseif ($output -match '(?i)applocker|application control|group policy|blocked by your administrator|not permitted') { $code = 'POLICY' }
        elseif ($output -match '(?i)access.*denied|unauthorized|permission') { $code = 'PERMISSION' }
        elseif ($output -match '(?i)Supported 64-bit Python') { $code = 'PYTHON_VERSION' }
        elseif ($output -match '(?i)could not create.*virtual environment|failed to create.*venv|python.*-m venv') { $code = 'VENV' }
        elseif ($output -match '(?i)no matching distribution|could not find a version|pip install|pip check|requirements\.txt') { $code = 'PACKAGES' }
        elseif ($output -match '(?i)cuda|cudnn|torch|torchvision|torchaudio|ctranslate2') { $code = 'GPU_PACKAGES' }
        elseif ($output -match '(?i)ffmpeg') { $code = 'FFMPEG' }
        elseif ($output -match '(?i)hugging.?face|pyannote|token') { $code = 'HUGGINGFACE' }
    }
    switch ($code) {
        'NETWORK_FILTER' { return "会社のWebフィルターがダウンロードを遮断した可能性があります。AI相談用ログとともに、python.org、pypi.org、files.pythonhosted.org、download.pytorch.org、huggingface.co へのHTTPS接続が必要とAIへ伝えてください。" }
        'PROXY' { return '会社のプロキシ認証が必要か、設定がWindowsに登録されていない可能性があります。AI相談用ログを添えて、Windowsのプロキシ設定・認証方法をAIへ質問してください。' }
        'TLS' { return 'TLS証明書の検証に失敗しました。企業の通信検査用証明書が必要な場合があります。検証を無効化せず、AI相談用ログを添えて証明書設定の確認方法をAIへ質問してください。' }
        'NETWORK' { return 'インターネットまたは社内ネットワークへ接続できません。接続後に再実行してください。会社PCではプロキシ・VPN・Webフィルターの設定も確認してください。' }
        'POLICY' { return '会社のアプリ実行ポリシー（AppLocker／Application Control／グループポリシー）により止められた可能性があります。AI相談用ログを添えて、ポリシーの状態を確認する安全な方法をAIへ質問してください。' }
        'PERMISSION' { return 'このユーザーの一時フォルダーまたはPythonの導入先へ書き込む権限がありません。AI相談用ログを添えて、管理者権限を要求せずに確認できる保存先・権限の確認方法をAIへ質問してください。' }
        'DISK' { return '空き容量が不足しています。Python・仮想環境・モデル用に十分な空き容量を確保してから再実行してください。' }
        'TEMP' { return 'Windowsの一時フォルダーを作成または書き込めません。空き容量、ユーザープロファイル、セキュリティソフトによる一時フォルダーの制限を確認してください。' }
        'FILE_LOCK' { return '必要なファイルが他のアプリにより使用中です。Gurumoji、Python、エクスプローラーのプレビュー、ウイルス対策ソフトの検査を閉じるか完了を待ってから再実行してください。' }
        'SECURITY_SOFTWARE' { return 'ウイルス対策ソフトまたはEDRがダウンロード・展開・実行を止めた可能性があります。保護を無効化せず、AI相談用ログを添えてPython公式インストーラーの実行可否をAIへ質問してください。' }
        'INTEGRITY' { return 'ダウンロードしたPythonのハッシュが公式値と一致しません。ネットワーク改変の可能性があるため導入を中止しました。AI相談用ログを添えて、安全な確認方法をAIへ質問してください。' }
        'SIGNATURE' { return 'Python Software Foundationの署名を確認できませんでした。安全のため導入を中止しました。AI相談用ログを添えて、安全な確認方法をAIへ質問してください。' }
        'PYTHON_VERSION' { return '対応する64 bit版Python 3.10〜3.13が見つかりません。Pythonの自動導入後は、このセットアップ画面を閉じて開き直してください。' }
        'VENV' { return 'プロジェクト用の仮想環境を作成できません。フォルダーへの書込権限、空き容量、既存の .venv が他のPythonで使用中でないかを確認してください。' }
        'PACKAGES' { return 'Pythonパッケージを取得または検証できません。ネットワーク・プロキシのほか、Pythonの対応版、会社のPyPI利用ポリシーを確認してください。AI相談用ログの最初のpipエラーをAIへ渡してください。' }
        'GPU_PACKAGES' { return 'GPU対応パッケージを設定できません。NVIDIA GPUやCUDAドライバーがないPCでもCPU動作は可能ですが、パッケージ取得が止められた場合はAI相談用ログを添えて download.pytorch.org への接続確認方法をAIへ質問してください。' }
        'FFMPEG' { return 'プロジェクト内FFmpegを準備できません。PyPIからの imageio-ffmpeg 取得や実行が、ネットワークまたはセキュリティポリシーで止められていないか確認してください。' }
        'HUGGINGFACE' { return 'Hugging Faceの利用条件・トークン・接続を確認してください。会社のネットワークでは huggingface.co へのHTTPS接続許可が必要な場合があります。' }
        default { return "$Title に失敗しました。AI相談用ログをAIへ貼り付けてください。ネットワーク制限・プロキシ・社内ポリシーがある場合は、必要な接続先と実行許可の確認方法を質問できます。" }
    }
}

function Protect-SetupLogLine {
    param([string]$Line)
    $safe = $Line
    $safe = [regex]::Replace($safe, '(?i)(bearer\s+)[^\s]+', '$1<redacted>')
    $safe = [regex]::Replace($safe, '(?i)(\b(?:token|api[_ -]?key|password|authorization)\b\s*[:=]\s*)[^\s,;]+', '$1<redacted>')
    $safe = [regex]::Replace($safe, '(?i)([?&](?:token|key|password)=)[^&\s]+', '$1<redacted>')
    return $safe
}

function Save-SetupSupportLog {
    param(
        [string]$Title,
        [int]$ExitCode,
        [string[]]$Lines
    )
    $directory = Join-Path $script:Root 'runtime\logs'
    [System.IO.Directory]::CreateDirectory($directory) | Out-Null
    $path = Join-Path $directory ('setup-error-{0}-{1}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss-fff'), $PID)
    $content = [System.Collections.Generic.List[string]]::new()
    $content.Add('Gurumoji setup diagnostic log')
    $content.Add("Action: $Title")
    $content.Add("Exit code: $ExitCode")
    $content.Add('Before sharing this log with an AI, remove any information you do not want to share, such as your name, PC name, local paths, or company network details.')
    $content.Add('--- process output ---')
    foreach ($line in $Lines) { $content.Add((Protect-SetupLogLine $line)) }
    [System.IO.File]::WriteAllLines($path, $content, [System.Text.UTF8Encoding]::new($false))
    return $path
}

function Show-SetupActionError {
    param(
        [string]$Title,
        [System.Management.Automation.ErrorRecord]$ErrorRecord
    )
    $message = "$Title を開始できませんでした: $($ErrorRecord.Exception.Message)"
    if ($null -ne $setupLog) { $setupLog.AppendText("$message`r`n") }
    [System.Windows.Forms.MessageBox]::Show($message, 'セットアップ エラー')
}

function Normalize-LmStudioUrl {
    param([string]$Value)
    $raw = $Value.Trim()
    if (-not $raw) { return 'http://127.0.0.1:1234/v1' }
    try {
        $uri = [System.Uri]$raw
    } catch {
        throw 'LM Studio URLの形式が正しくありません。'
    }
    $path = $uri.AbsolutePath.TrimEnd('/')
    $parsedIp = $null
    $isIpAddress = [System.Net.IPAddress]::TryParse(
        $uri.Host.Trim(@([char]'[', [char]']')),
        [ref]$parsedIp
    )
    $isAllowedLoopback = $isIpAddress -and (
        [System.Net.IPAddress]::Loopback.Equals($parsedIp) -or
        [System.Net.IPAddress]::IPv6Loopback.Equals($parsedIp)
    )
    if (
        -not $uri.IsAbsoluteUri -or
        $uri.Scheme -notin @('http', 'https') -or
        -not $isAllowedLoopback -or
        $uri.IsDefaultPort -or
        $uri.Port -lt 1 -or
        $uri.Port -gt 65535 -or
        $uri.Query -or
        $uri.Fragment -or
        $path -notin @('', '/v1')
    ) {
        throw 'LM Studio URLは http://127.0.0.1:1234/v1 または http://[::1]:1234/v1 のように、このPCのループバックだけを指定してください。'
    }
    $authority = if ($parsedIp.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetworkV6) {
        '[::1]:{0}' -f $uri.Port
    } else {
        '127.0.0.1:{0}' -f $uri.Port
    }
    return ('{0}://{1}/v1' -f $uri.Scheme, $authority)
}

function New-WorkerProcess {
    param(
        [string]$Command,
        [hashtable]$Environment = @{}
    )
    $start = [System.Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $env:ComSpec
    $start.Arguments = "/d /c $Command"
    $start.WorkingDirectory = $script:Root
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($entry in $Environment.GetEnumerator()) {
        $start.EnvironmentVariables[$entry.Key] = [string]$entry.Value
    }
    return $start
}

function Start-BackgroundCommand {
    param(
        [string]$Title,
        [string]$Command,
        [hashtable]$Environment = @{}
    )
    if ($null -ne $script:ActiveProcess) {
        [System.Windows.Forms.MessageBox]::Show('別のセットアップ処理が実行中です。完了を待ってください。', 'セットアップ')
        return
    }
    $start = New-WorkerProcess -Command $Command -Environment $Environment
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $start
    $queue = [System.Collections.Concurrent.ConcurrentQueue[string]]::new()
    $onOutput = [System.Diagnostics.DataReceivedEventHandler]{
        param($source, $data)
        if ($null -ne $data.Data) { $queue.Enqueue($data.Data) }
    }
    $process.add_OutputDataReceived($onOutput)
    $process.add_ErrorDataReceived($onOutput)
    if (-not $process.Start()) { throw 'セットアップ処理を開始できませんでした。' }
    $script:ActiveProcess = $process
    $script:ActiveOutput = $queue
    $script:ActiveLines = [System.Collections.Generic.List[string]]::new()
    $script:ActiveTitle = $Title
    $buttonCheck.Enabled = $false
    $buttonInstallPrerequisites.Enabled = $false
    $buttonInstallApp.Enabled = $false
    $buttonLaunch.Enabled = $false
    $setupLog.AppendText("`r`n--- $Title を開始 ---`r`n")
    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()
    $script:ProcessPollTimer.Start()
}

$form = [System.Windows.Forms.Form]::new()
$form.Text = 'Gurumoji セットアップ'
$form.StartPosition = 'CenterScreen'
$form.MinimumSize = [System.Drawing.Size]::new(820, 700)
$form.Size = [System.Drawing.Size]::new(920, 820)
$form.Font = [System.Drawing.Font]::new('Yu Gothic UI', 9)

$rootPanel = [System.Windows.Forms.TableLayoutPanel]::new()
$rootPanel.Dock = 'Fill'
$rootPanel.AutoScroll = $true
$rootPanel.ColumnCount = 1
$rootPanel.Padding = [System.Windows.Forms.Padding]::new(18)
$form.Controls.Add($rootPanel)

$header = [System.Windows.Forms.Label]::new()
$header.Text = 'Gurumoji — はじめてのセットアップ'
$header.AutoSize = $true
$header.Font = [System.Drawing.Font]::new('Yu Gothic UI', 18, [System.Drawing.FontStyle]::Bold)
$rootPanel.Controls.Add($header)

$description = [System.Windows.Forms.Label]::new()
$description.Text = 'この画面だけで、Python の確認・アプリ環境の作成・tokens.json の設定を行えます。FFmpeg はアプリ環境に自動導入されます。秘密鍵は画面上で伏せて表示し、ログには書き込みません。'
$description.AutoSize = $true
$description.MaximumSize = [System.Drawing.Size]::new(830, 0)
$description.Margin = [System.Windows.Forms.Padding]::new(3, 6, 3, 12)
$rootPanel.Controls.Add($description)

$environmentGroup = [System.Windows.Forms.GroupBox]::new()
$environmentGroup.Text = '1. 実行環境'
$environmentGroup.Dock = 'Top'
$environmentGroup.AutoSize = $false
$environmentGroup.Height = 155
$environmentGroup.Padding = [System.Windows.Forms.Padding]::new(12)
$rootPanel.Controls.Add($environmentGroup)

$statusBox = [System.Windows.Forms.TextBox]::new()
$statusBox.Location = [System.Drawing.Point]::new(12, 24)
$statusBox.Anchor = 'Top,Left,Right'
$statusBox.Size = [System.Drawing.Size]::new(850, 92)
$statusBox.Multiline = $true
$statusBox.ReadOnly = $true
$statusBox.BorderStyle = 'FixedSingle'
$statusBox.Height = 96
$statusBox.Text = Get-EnvironmentReport
$environmentGroup.Controls.Add($statusBox)

$environmentButtons = [System.Windows.Forms.FlowLayoutPanel]::new()
$environmentButtons.Location = [System.Drawing.Point]::new(12, 124)
$environmentButtons.AutoSize = $true
$environmentButtons.FlowDirection = 'LeftToRight'
$environmentButtons.Padding = [System.Windows.Forms.Padding]::new(0, 10, 0, 0)
$environmentGroup.Controls.Add($environmentButtons)

$buttonCheck = [System.Windows.Forms.Button]::new()
$buttonCheck.Text = '再チェック'
$buttonCheck.AutoSize = $true
$buttonCheck.add_Click({ $statusBox.Text = Get-EnvironmentReport })
$environmentButtons.Controls.Add($buttonCheck)

$buttonInstallPrerequisites = [System.Windows.Forms.Button]::new()
$buttonInstallPrerequisites.Text = 'Python を自動インストール'
$buttonInstallPrerequisites.AutoSize = $true
$buttonInstallPrerequisites.add_Click({
    try {
        if (-not (Test-Path -LiteralPath $script:PythonInstallerScript)) {
            throw 'Python インストーラーが見つかりません。setup_gui.ps1 と install_python.ps1 が同じ scripts フォルダーにあることを確認してください。'
        }
        $choice = [System.Windows.Forms.MessageBox]::Show(
            'Python 3.13.15（64 bit）を公式の python.org からダウンロードし、このユーザー用に導入します。約30 MBのダウンロード後、セットアップ画面を閉じて開き直してください。続けますか？',
            'Python を自動インストール',
            [System.Windows.Forms.MessageBoxButtons]::YesNo,
            [System.Windows.Forms.MessageBoxIcon]::Question
        )
        if ($choice -ne [System.Windows.Forms.DialogResult]::Yes) { return }
        $command = 'powershell -NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $script:PythonInstallerScript
        Start-BackgroundCommand -Title 'Python 3.13.15 のインストール' -Command $command
    } catch {
        Show-SetupActionError -Title 'Python の自動インストール' -ErrorRecord $_
    }
})
$environmentButtons.Controls.Add($buttonInstallPrerequisites)

$openHuggingFace = [System.Windows.Forms.Button]::new()
$openHuggingFace.Text = 'Hugging Face の利用条件を開く'
$openHuggingFace.AutoSize = $true
$openHuggingFace.add_Click({
    Start-Process 'https://huggingface.co/pyannote/speaker-diarization-community-1'
    Start-Process 'https://huggingface.co/pyannote/segmentation-3.0'
})
$environmentButtons.Controls.Add($openHuggingFace)

$tokenGroup = [System.Windows.Forms.GroupBox]::new()
$tokenGroup.Text = '2. 認証・ローカルLLM設定（必要なものだけ）'
$tokenGroup.Dock = 'Top'
$tokenGroup.AutoSize = $false
$tokenGroup.Height = 410
$tokenGroup.Padding = [System.Windows.Forms.Padding]::new(12)
$tokenGroup.Margin = [System.Windows.Forms.Padding]::new(3, 16, 3, 3)
$rootPanel.Controls.Add($tokenGroup)

$tokenTable = [System.Windows.Forms.TableLayoutPanel]::new()
$tokenTable.Location = [System.Drawing.Point]::new(12, 24)
$tokenTable.Anchor = 'Top,Left,Right'
$tokenTable.AutoSize = $false
$tokenTable.Size = [System.Drawing.Size]::new(850, 250)
$tokenTable.ColumnCount = 2
$tokenTable.ColumnStyles.Add([System.Windows.Forms.ColumnStyle]::new([System.Windows.Forms.SizeType]::Absolute, 220))
$tokenTable.ColumnStyles.Add([System.Windows.Forms.ColumnStyle]::new([System.Windows.Forms.SizeType]::Percent, 100))
$tokenGroup.Controls.Add($tokenTable)

$settings = Get-JsonSettings
function Add-SettingRow {
    param([string]$Label, [string]$Value, [bool]$Secret = $false)
    $row = $tokenTable.RowCount
    $tokenTable.RowCount++
    $name = [System.Windows.Forms.Label]::new()
    $name.Text = $Label
    $name.AutoSize = $true
    $name.Anchor = 'Left'
    $input = [System.Windows.Forms.TextBox]::new()
    $input.Text = $Value
    $input.Dock = 'Fill'
    $input.Margin = [System.Windows.Forms.Padding]::new(4)
    if ($Secret) { $input.UseSystemPasswordChar = $true }
    $tokenTable.Controls.Add($name, 0, $row)
    $tokenTable.Controls.Add($input, 1, $row)
    return $input
}

$hfValue = Get-SettingText $settings 'huggingface_token'
if (-not $hfValue) { $hfValue = Get-SettingText $settings 'hf_token' }
$hfToken = Add-SettingRow 'Hugging Face token（必須）' $hfValue $true
$openAiKey = Add-SettingRow 'OpenAI API key（任意）' (Get-SettingText $settings 'openai_api_key') $true
$googleKey = Add-SettingRow 'Google Gemini API key（任意）' (Get-SettingText $settings 'google_api_key') $true
$typeSafeKey = Add-SettingRow 'TypeSafe API key（Jev比較用）' (Get-SettingText $settings 'typesafe_api_key') $true
$typeSafeModel = Add-SettingRow 'TypeSafe model' (Get-SettingText $settings 'typesafe_model' 'jev-latest') $false
$lmStudioUrl = Add-SettingRow 'LM Studio URL' (Get-SettingText $settings 'lmstudio_base_url' 'http://127.0.0.1:1234/v1') $false
$lmStudioModel = Add-SettingRow 'LM Studio model（空欄でも可）' (Get-SettingText $settings 'lmstudio_model') $false
$lmStudioKey = Add-SettingRow 'LM Studio API key（認証時のみ）' (Get-SettingText $settings 'lmstudio_api_key') $true

$tokenHelp = [System.Windows.Forms.Label]::new()
$tokenHelp.Text = 'Hugging Face は pyannote の利用条件に同意後の read token が必要です。TypeSafe は Jevで修正要否を比較する場合だけ必要です。LM Studio は既定のまま Developer → Start server を有効にし、モデルはアプリ画面上部の LM Studio ライトから選べます。'
$tokenHelp.AutoSize = $true
$tokenHelp.MaximumSize = [System.Drawing.Size]::new(820, 0)
$tokenHelp.Margin = [System.Windows.Forms.Padding]::new(3, 10, 3, 3)
$tokenHelp.Location = [System.Drawing.Point]::new(12, 285)
$tokenGroup.Controls.Add($tokenHelp)

$buttonSave = [System.Windows.Forms.Button]::new()
$buttonSave.Text = '設定を保存'
$buttonSave.AutoSize = $true
$buttonSave.Margin = [System.Windows.Forms.Padding]::new(3, 10, 3, 3)
$buttonSave.Location = [System.Drawing.Point]::new(12, 352)
$buttonSave.add_Click({
    try {
        $next = Get-JsonSettings
        Set-SettingValue $next 'huggingface_token' $hfToken.Text
        Set-SettingValue $next 'openai_api_key' $openAiKey.Text
        Set-SettingValue $next 'google_api_key' $googleKey.Text
        Set-SettingValue $next 'typesafe_api_key' $typeSafeKey.Text
        Set-SettingValue $next 'typesafe_model' $typeSafeModel.Text
        Set-SettingValue $next 'lmstudio_base_url' (Normalize-LmStudioUrl $lmStudioUrl.Text)
        Set-SettingValue $next 'lmstudio_model' $lmStudioModel.Text
        Set-SettingValue $next 'lmstudio_api_key' $lmStudioKey.Text
        Save-JsonSettings $next
        $statusBox.Text = Get-EnvironmentReport
        [System.Windows.Forms.MessageBox]::Show('tokens.json に保存しました。', 'セットアップ')
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, '保存できません')
    }
})
$tokenGroup.Controls.Add($buttonSave)

$applicationGroup = [System.Windows.Forms.GroupBox]::new()
$applicationGroup.Text = '3. アプリ環境を作成して起動'
$applicationGroup.Dock = 'Top'
$applicationGroup.AutoSize = $false
$applicationGroup.Height = 145
$applicationGroup.Padding = [System.Windows.Forms.Padding]::new(12)
$applicationGroup.Margin = [System.Windows.Forms.Padding]::new(3, 16, 3, 3)
$rootPanel.Controls.Add($applicationGroup)

$applicationHelp = [System.Windows.Forms.Label]::new()
$applicationHelp.Text = '「アプリ環境を作成」は、このフォルダー内に .venv、必要なPythonパッケージ、FFmpeg を導入します。初回は大きなダウンロードがあります。Pythonを今インストールした場合は、この画面を一度閉じて開き直してください。'
$applicationHelp.AutoSize = $true
$applicationHelp.MaximumSize = [System.Drawing.Size]::new(820, 0)
$applicationHelp.Location = [System.Drawing.Point]::new(12, 24)
$applicationGroup.Controls.Add($applicationHelp)

$applicationButtons = [System.Windows.Forms.FlowLayoutPanel]::new()
$applicationButtons.Location = [System.Drawing.Point]::new(12, 88)
$applicationButtons.AutoSize = $true
$applicationButtons.FlowDirection = 'LeftToRight'
$applicationButtons.Padding = [System.Windows.Forms.Padding]::new(0, 10, 0, 0)
$applicationGroup.Controls.Add($applicationButtons)

$buttonInstallApp = [System.Windows.Forms.Button]::new()
$buttonInstallApp.Text = 'アプリ環境を作成'
$buttonInstallApp.AutoSize = $true
$buttonInstallApp.add_Click({
    try {
        if (-not (Test-Path -LiteralPath $script:RunBatch)) { throw 'run.bat が見つかりません。' }
        $next = Get-JsonSettings
        Set-SettingValue $next 'huggingface_token' $hfToken.Text
        Set-SettingValue $next 'openai_api_key' $openAiKey.Text
        Set-SettingValue $next 'google_api_key' $googleKey.Text
        Set-SettingValue $next 'lmstudio_base_url' (Normalize-LmStudioUrl $lmStudioUrl.Text)
        Set-SettingValue $next 'lmstudio_model' $lmStudioModel.Text
        Set-SettingValue $next 'lmstudio_api_key' $lmStudioKey.Text
        Save-JsonSettings $next
        $environment = @{
            MOJIOKOSI_LAUNCH_WORKER = '1'
            MOJIOKOSI_NO_PAUSE = '1'
            MOJIOKOSI_SKIP_UPDATE_CHECK = '1'
            MOJIOKOSI_SETUP_ONLY = '1'
        }
        Start-BackgroundCommand -Title 'アプリ環境の作成' -Command ('call "{0}"' -f $script:RunBatch) -Environment $environment
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'セットアップを開始できません')
    }
})
$applicationButtons.Controls.Add($buttonInstallApp)

$buttonLaunch = [System.Windows.Forms.Button]::new()
$buttonLaunch.Text = 'Gurumoji を起動'
$buttonLaunch.AutoSize = $true
$buttonLaunch.add_Click({
    try {
        if (-not (Test-Path -LiteralPath $script:RunBatch)) { throw 'run.bat が見つかりません。' }
        $next = Get-JsonSettings
        Set-SettingValue $next 'huggingface_token' $hfToken.Text
        Set-SettingValue $next 'openai_api_key' $openAiKey.Text
        Set-SettingValue $next 'google_api_key' $googleKey.Text
        Set-SettingValue $next 'lmstudio_base_url' (Normalize-LmStudioUrl $lmStudioUrl.Text)
        Set-SettingValue $next 'lmstudio_model' $lmStudioModel.Text
        Set-SettingValue $next 'lmstudio_api_key' $lmStudioKey.Text
        Save-JsonSettings $next
        Start-Process -FilePath $env:ComSpec -WorkingDirectory $script:Root -ArgumentList @('/d', '/k', ('call "{0}"' -f $script:RunBatch))
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, '起動できません')
    }
})
$applicationButtons.Controls.Add($buttonLaunch)

$logGroup = [System.Windows.Forms.GroupBox]::new()
$logGroup.Text = 'セットアップログ（秘密鍵は表示しません）'
$logGroup.Dock = 'Top'
$logGroup.Height = 210
$logGroup.Padding = [System.Windows.Forms.Padding]::new(10)
$logGroup.Margin = [System.Windows.Forms.Padding]::new(3, 16, 3, 3)
$rootPanel.Controls.Add($logGroup)

$setupLog = [System.Windows.Forms.TextBox]::new()
$setupLog.Dock = 'Fill'
$setupLog.Multiline = $true
$setupLog.ReadOnly = $true
$setupLog.ScrollBars = 'Both'
$setupLog.WordWrap = $false
$setupLog.Font = [System.Drawing.Font]::new('Consolas', 9)
$logGroup.Controls.Add($setupLog)

$script:ProcessPollTimer = [System.Windows.Forms.Timer]::new()
$script:ProcessPollTimer.Interval = 120
$script:ProcessPollTimer.add_Tick({
    if ($null -eq $script:ActiveProcess -or $null -eq $script:ActiveOutput) {
        $script:ProcessPollTimer.Stop()
        return
    }
    $line = ''
    while ($script:ActiveOutput.TryDequeue([ref]$line)) {
        $setupLog.AppendText($line + [Environment]::NewLine)
        $script:ActiveLines.Add($line)
    }
    $setupLog.SelectionStart = $setupLog.TextLength
    $setupLog.ScrollToCaret()
    if (-not $script:ActiveProcess.HasExited) { return }
    $script:ActiveProcess.WaitForExit()
    while ($script:ActiveOutput.TryDequeue([ref]$line)) {
        $setupLog.AppendText($line + [Environment]::NewLine)
        $script:ActiveLines.Add($line)
    }
    $exitCode = $script:ActiveProcess.ExitCode
    $title = $script:ActiveTitle
    $lines = @($script:ActiveLines)
    $script:ActiveProcess.Dispose()
    $script:ActiveProcess = $null
    $script:ActiveOutput = $null
    $script:ActiveLines = $null
    $script:ActiveTitle = ''
    $script:ProcessPollTimer.Stop()
    $buttonCheck.Enabled = $true
    $buttonInstallPrerequisites.Enabled = $true
    $buttonInstallApp.Enabled = $true
    $buttonLaunch.Enabled = $true
    $setupLog.AppendText("`r`n$title が終了しました（終了コード: $exitCode）。`r`n")
    Refresh-ProcessPath
    $statusBox.Text = Get-EnvironmentReport
    if ($exitCode -eq 0) {
        [System.Windows.Forms.MessageBox]::Show("$title が完了しました。", 'セットアップ')
    } else {
        $guidance = Get-SetupFailureGuidance -Title $title -Lines $lines
        try {
            $supportLog = Save-SetupSupportLog -Title $title -ExitCode $exitCode -Lines $lines
            $aiHint = "AI相談用ログを保存しました: $supportLog`r`nこのファイルを開き、共有したくない名前・PC名・パス・社内ネットワーク情報を削除してから、エラー内容と一緒にAIへ貼り付けてください。APIキー・トークン・パスワードは共有しないでください。"
        } catch {
            $aiHint = "AI相談用ログをファイルへ保存できませんでした: $($_.Exception.Message)`r`n画面下部のセットアップログをコピーし、共有したくない情報を削除してからAIへ貼り付けてください。APIキー・トークン・パスワードは共有しないでください。"
        }
        $setupLog.AppendText("対処: $guidance`r`n$aiHint`r`n")
        [System.Windows.Forms.MessageBox]::Show("$guidance`r`n`r`n$aiHint", 'セットアップ エラー')
    }
})

if (Test-Path -LiteralPath $script:VisualizationShortcutScript) {
    try {
        $shortcutMessage = @(& $script:VisualizationShortcutScript)
        foreach ($message in $shortcutMessage) { $setupLog.AppendText($message + [Environment]::NewLine) }
    } catch {
        $setupLog.AppendText("可視化用Obsidianショートカットを作成できませんでした: $($_.Exception.Message)`r`n")
    }
}

[void]$form.ShowDialog()
