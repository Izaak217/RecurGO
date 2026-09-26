# RecurGO v0.1.4 - source-local or installed user-data Ollama service management.
[CmdletBinding()]
param(
    [ValidateSet('Start', 'Pull', 'Status', 'Stop')]
    [string]$Action = 'Status',
    [string]$Model = 'qwen3:4b-instruct-2507-q4_K_M',
    [string]$DataRoot = '',
    [switch]$UseProxy
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
if ($DataRoot) {
    if (-not [IO.Path]::IsPathRooted($DataRoot)) {
        throw "DataRoot must be an absolute path: $DataRoot"
    }
    $storageRoot = [IO.Path]::GetFullPath($DataRoot)
    $runtimeRoot = Join-Path $storageRoot 'ollama'
} else {
    $storageRoot = $projectRoot
    $runtimeRoot = Join-Path $storageRoot 'runtime\ollama'
}
$executable = Join-Path $runtimeRoot 'v0.34.3\ollama.exe'
$recordPath = Join-Path $runtimeRoot 'service.json'
$baseUrl = 'http://127.0.0.1:11434'
$expectedVersion = '0.34.3'

function Assert-ManagedPath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $prefix = $storageRoot.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing a path outside the managed Ollama storage root: $full"
    }
    $cursor = $full
    while ($cursor -and -not $cursor.Equals($storageRoot, [StringComparison]::OrdinalIgnoreCase)) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing a junction or symbolic link in a writable/runtime path: $cursor"
            }
        }
        $cursor = Split-Path -Parent $cursor
    }
    return $full
}

function Ensure-ManagedDirectory([string]$Path) {
    $full = Assert-ManagedPath $Path
    if (Test-Path -LiteralPath $full) {
        if (-not (Test-Path -LiteralPath $full -PathType Container)) {
            throw "Expected a directory: $full"
        }
    } else {
        [IO.Directory]::CreateDirectory($full) | Out-Null
    }
}

function Read-ServiceRecord {
    $null = Assert-ManagedPath $recordPath
    if (-not (Test-Path -LiteralPath $recordPath)) { return $null }
    try {
        return (Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json)
    } catch {
        throw "Cannot read service record $recordPath. No process was changed. $($_.Exception.Message)"
    }
}

function Get-RecordedStartUtcTicks($Value) {
    # v0.1.2: PS 5.1 keeps ISO JSON dates as strings; PS 7 may deserialize DateTime.
    $timestamp = [DateTime]::MinValue
    if ($Value -is [DateTime]) {
        $timestamp = $Value
    } elseif ($Value -is [string]) {
        if (-not [DateTime]::TryParseExact(
            $Value, 'o', [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind, [ref]$timestamp)) {
            throw 'Service record has an invalid startedAtUtc; refusing to control a process.'
        }
    } else {
        throw 'Service record has an invalid startedAtUtc; refusing to control a process.'
    }
    if ($timestamp.Kind -eq [DateTimeKind]::Unspecified) {
        throw 'Service record startedAtUtc has no timezone; refusing to control a process.'
    }
    return $timestamp.ToUniversalTime().Ticks
}

function Get-ManagedProcess($Record) {
    if ($null -eq $Record) { return $null }
    foreach ($field in @('processId', 'executable', 'startedAtUtc', 'networkMode')) {
        if ($null -eq $Record.PSObject.Properties[$field]) {
            throw "Service record is missing '$field'; refusing to control a process."
        }
    }
    $recordedStartTicks = Get-RecordedStartUtcTicks $Record.startedAtUtc
    $process = Get-Process -Id ([int]$Record.processId) -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $null }
    $expectedPath = Assert-ManagedPath $executable
    if (-not $expectedPath.Equals([string]$Record.executable, [StringComparison]::OrdinalIgnoreCase) -or
        -not $expectedPath.Equals([string]$process.Path, [StringComparison]::OrdinalIgnoreCase) -or
        $process.StartTime.ToUniversalTime().Ticks -ne $recordedStartTicks) {
        throw "PID $($Record.processId) is not the recorded project Ollama process. Refusing to control it."
    }
    return $process
}

function Get-PortListeners {
    return @(Get-NetTCPConnection -State Listen -LocalPort 11434 -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalAddress -in @('127.0.0.1', '0.0.0.0', '::', '::1') })
}

function Assert-ManagedListener($Process) {
    $listeners = @(Get-PortListeners)
    if ($listeners.Count -eq 0) { throw 'The project Ollama process is not listening on port 11434.' }
    $foreign = @($listeners | Where-Object { $_.OwningProcess -ne $Process.Id })
    if ($foreign.Count -gt 0) {
        throw 'Port 11434 has a listener owned by another process; no request or termination was sent.'
    }
}

function Read-ApiVersion {
    Add-Type -AssemblyName System.Net.Http
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.UseProxy = $false
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(2)
    try {
        $body = $client.GetStringAsync("$baseUrl/api/version").GetAwaiter().GetResult()
        return [string](($body | ConvertFrom-Json).version)
    } finally {
        $client.Dispose()
        $handler.Dispose()
    }
}

function Write-ServiceRecord($Record) {
    $full = Assert-ManagedPath $recordPath
    $json = $Record | ConvertTo-Json -Depth 5
    [IO.File]::WriteAllText($full, $json + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
}

function Invoke-WithOllamaEnvironment([scriptblock]$Operation) {
    $profileDir = Join-Path $runtimeRoot 'profile'
    $values = @{
        USERPROFILE = $profileDir
        LOCALAPPDATA = Join-Path $profileDir 'AppData\Local'
        APPDATA = Join-Path $profileDir 'AppData\Roaming'
        TEMP = Join-Path $runtimeRoot 'tmp'
        TMP = Join-Path $runtimeRoot 'tmp'
        TMPDIR = Join-Path $runtimeRoot 'tmp'
        CUDA_CACHE_PATH = Join-Path $runtimeRoot 'cuda-cache'
        OLLAMA_MODELS = Join-Path $runtimeRoot 'models'
        OLLAMA_HOST = '127.0.0.1:11434'
        OLLAMA_NO_CLOUD = '1'
        OLLAMA_NOHISTORY = '1'
        OLLAMA_DEBUG_LOG_REQUESTS = 'false'
        OLLAMA_MAX_LOADED_MODELS = '1'
        OLLAMA_NUM_PARALLEL = '1'
        OLLAMA_NOPRUNE = '1'
        NO_PROXY = '127.0.0.1,localhost,::1'
    }
    if ($UseProxy) {
        if (-not ([Environment]::GetEnvironmentVariable('HTTPS_PROXY', 'Process')) -and
            -not ([Environment]::GetEnvironmentVariable('HTTP_PROXY', 'Process'))) {
            throw '-UseProxy requires an existing process HTTPS_PROXY or HTTP_PROXY setting; no proxy is configured.'
        }
    } else {
        $values['HTTP_PROXY'] = $null
        $values['HTTPS_PROXY'] = $null
        $values['ALL_PROXY'] = $null
        $values['NO_PROXY'] = '*'
    }
    foreach ($name in @('USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'TEMP', 'TMP', 'TMPDIR', 'CUDA_CACHE_PATH', 'OLLAMA_MODELS')) {
        Ensure-ManagedDirectory $values[$name]
    }
    $saved = @{}
    try {
        foreach ($entry in $values.GetEnumerator()) {
            $saved[$entry.Key] = [Environment]::GetEnvironmentVariable($entry.Key, 'Process')
            [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
        }
        & $Operation
    } finally {
        foreach ($entry in $saved.GetEnumerator()) {
            [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
        }
    }
}

function Stop-ManagedProcess($Process) {
    # Recheck both executable and creation time immediately before terminating its tree.
    $fresh = Get-ManagedProcess (Read-ServiceRecord)
    if ($null -eq $fresh -or $fresh.Id -ne $Process.Id) {
        throw 'The recorded service changed before Stop; nothing was terminated.'
    }
    & "$env:SystemRoot\System32\taskkill.exe" /PID $fresh.Id /T /F
    if ($LASTEXITCODE -ne 0) { throw "Could not stop the project Ollama process (taskkill exit $LASTEXITCODE)." }
    if (-not $fresh.WaitForExit(10000)) { throw 'The project Ollama process has not exited yet.' }
}

$null = Assert-ManagedPath $runtimeRoot
$null = Assert-ManagedPath $executable
$record = Read-ServiceRecord
$managed = Get-ManagedProcess $record
$requestedMode = if ($UseProxy) { 'proxy' } else { 'direct' }

switch ($Action) {
    'Status' {
        $listeners = @(Get-PortListeners)
        $version = $null
        $apiStatus = 'not contacted'
        if ($null -ne $managed) {
            try {
                Assert-ManagedListener $managed
                $version = Read-ApiVersion
                $apiStatus = 'ready'
            } catch { $apiStatus = $_.Exception.Message }
        }
        [pscustomobject]@{
            ScriptVersion = '0.1.4'
            Executable = $executable
            Installed = Test-Path -LiteralPath $executable -PathType Leaf
            ProjectServiceRunning = ($null -ne $managed)
            ProcessId = $(if ($null -ne $managed) { $managed.Id } else { $null })
            Endpoint = $baseUrl
            ApiStatus = $apiStatus
            ApiVersion = $version
            ExpectedVersion = $expectedVersion
            NetworkMode = $(if ($null -ne $record) { $record.networkMode } else { 'not started' })
            PortListenerProcessIds = (($listeners | Select-Object -ExpandProperty OwningProcess -Unique) -join ', ')
            StateFile = $recordPath
        }
    }
    'Start' {
        if ($null -ne $managed) {
            Assert-ManagedListener $managed
            if ($record.networkMode -ne $requestedMode) {
                throw "The project service uses $($record.networkMode) networking. Stop it first, then Start with the requested proxy option."
            }
            $version = Read-ApiVersion
            if ($version -ne $expectedVersion) { throw "Unexpected Ollama API version: $version" }
            $record.status = 'ready'
            Write-ServiceRecord $record
            Write-Output "Project Ollama is already ready at $baseUrl (PID $($managed.Id), $requestedMode)."
            break
        }
        $listeners = @(Get-PortListeners)
        if ($listeners.Count -gt 0) {
            $owners = ($listeners | Select-Object -ExpandProperty OwningProcess -Unique) -join ', '
            throw "Port 11434 is occupied by PID(s) $owners. No process was stopped or replaced."
        }
        if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
            throw "Portable Ollama is not installed at $executable. Extract the verified v0.34.3 CLI archive there first."
        }
        Ensure-ManagedDirectory (Join-Path $runtimeRoot 'logs')
        $stamp = (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
        $stdoutLog = Assert-ManagedPath (Join-Path $runtimeRoot "logs\serve-$stamp.stdout.log")
        $stderrLog = Assert-ManagedPath (Join-Path $runtimeRoot "logs\serve-$stamp.stderr.log")
        if ((Test-Path -LiteralPath $stdoutLog) -or (Test-Path -LiteralPath $stderrLog)) {
            throw 'Refusing to overwrite an existing log file.'
        }
        Invoke-WithOllamaEnvironment {
            $started = Start-Process -FilePath $executable -ArgumentList 'serve' -WorkingDirectory $runtimeRoot `
                -WindowStyle Hidden -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
            $newRecord = [pscustomobject]@{
                scriptVersion = '0.1.4'
                processId = $started.Id
                executable = $executable
                startedAtUtc = $started.StartTime.ToUniversalTime().ToString('o')
                networkMode = $requestedMode
                endpoint = $baseUrl
                stdoutLog = $stdoutLog
                stderrLog = $stderrLog
                status = 'starting'
                stoppedAtUtc = $null
            }
            Write-ServiceRecord $newRecord
        }
        $deadline = (Get-Date).AddSeconds(30)
        $ready = $false
        while ((Get-Date) -lt $deadline) {
            $record = Read-ServiceRecord
            $managed = Get-ManagedProcess $record
            if ($null -eq $managed) { throw "Ollama exited during startup. Inspect $stderrLog" }
            try {
                Assert-ManagedListener $managed
                $version = Read-ApiVersion
                if ($version -ne $expectedVersion) { throw "Unexpected Ollama API version: $version" }
                $ready = $true
                break
            } catch { Start-Sleep -Milliseconds 250 }
        }
        if (-not $ready) {
            throw "Ollama did not become ready in 30 seconds. It remains tracked; use Status or Stop. Inspect $stderrLog"
        }
        $record.status = 'ready'
        Write-ServiceRecord $record
        Write-Output "Project Ollama $version is ready at $baseUrl (PID $($managed.Id), $requestedMode)."
        Write-Output "Logs: $stdoutLog ; $stderrLog"
    }
    'Pull' {
        if ($null -eq $managed) { throw 'No managed project Ollama service is running. Use -Action Start first.' }
        Assert-ManagedListener $managed
        if ($record.networkMode -ne $requestedMode) {
            throw "Pull downloads run inside serve, which currently uses $($record.networkMode) networking. Use Stop, Start with the intended -UseProxy option, then Pull with the same option."
        }
        $version = Read-ApiVersion
        if ($version -ne $expectedVersion) { throw "Unexpected Ollama API version: $version" }
        if ([string]::IsNullOrWhiteSpace($Model) -or $Model.StartsWith('-')) { throw 'A valid model tag is required.' }
        Write-Output "Pulling $Model through the project service ($requestedMode). Progress below is Ollama's own progress."
        Invoke-WithOllamaEnvironment {
            & $executable pull $Model
            if ($LASTEXITCODE -ne 0) {
                throw "Ollama pull failed (exit $LASTEXITCODE). For a direct connection failure, Stop then Start -UseProxy and Pull -UseProxy with process HTTP(S)_PROXY configured."
            }
        }
    }
    'Stop' {
        if ($null -eq $managed) {
            Write-Output 'The recorded project Ollama service is not running. No other process was touched.'
            break
        }
        Stop-ManagedProcess $managed
        $record.status = 'stopped'
        $record.stoppedAtUtc = [DateTime]::UtcNow.ToString('o')
        Write-ServiceRecord $record
        Write-Output "Stopped project Ollama PID $($managed.Id). State, models and logs were retained."
    }
}
