param(
    [switch]$ImportOnly,
    [switch]$FullLoad,
    [int]$WaitForReadySeconds = 360
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Exe = Join-Path $Root "dist\LocalVoiceDictation\LocalVoiceDictation.exe"

if (-not (Test-Path $Exe)) {
    throw "Packaged executable not found: $Exe"
}

if (-not $ImportOnly -and -not $FullLoad) {
    $ImportOnly = $true
}

function New-TestRoot {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $path = Join-Path $env:TEMP "lvd-exe-smoke-$stamp"
    New-Item -ItemType Directory -Path $path | Out-Null
    return $path
}

function Copy-ModelsAsHardLinks {
    param(
        [Parameter(Mandatory = $true)][string]$SourceModels,
        [Parameter(Mandatory = $true)][string]$TargetModels
    )

    New-Item -ItemType Directory -Path $TargetModels -Force | Out-Null

    Get-ChildItem -LiteralPath $SourceModels -Recurse -Directory | ForEach-Object {
        $relative = $_.FullName.Substring($SourceModels.Length).TrimStart("\")
        New-Item -ItemType Directory -Path (Join-Path $TargetModels $relative) -Force | Out-Null
    }

    Get-ChildItem -LiteralPath $SourceModels -Recurse -File | ForEach-Object {
        $relative = $_.FullName.Substring($SourceModels.Length).TrimStart("\")
        $target = Join-Path $TargetModels $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        New-Item -ItemType HardLink -Path $target -Target $_.FullName | Out-Null
    }
}

function Get-LogTail {
    param([string]$LogPath, [int]$Lines = 80)
    if (Test-Path $LogPath) {
        return Get-Content -LiteralPath $LogPath -Tail $Lines
    }
    return @()
}

$testRoot = New-TestRoot
$logPath = Join-Path $testRoot "voice_dictation.log"
$env:LOCAL_VOICE_DICTATION_APP_ROOT = $testRoot
$env:LOCAL_VOICE_DICTATION_MUTEX_NAME = "Local\LocalVoiceDictation.PackageSmoke.$PID"

if ($ImportOnly) {
    $env:LOCAL_VOICE_DICTATION_SMOKE_IMPORT = "1"
    $process = Start-Process -FilePath $Exe -PassThru -Wait -WindowStyle Hidden
    $tail = Get-LogTail -LogPath $logPath -Lines 10
    [PSCustomObject]@{
        test_root = $testRoot
        mode = "import"
        exit_code = $process.ExitCode
        log_exists = Test-Path $logPath
        passed = ($process.ExitCode -eq 0 -and ($tail -match "package smoke import ok"))
    }
    $tail
    exit $(if ($process.ExitCode -eq 0 -and ($tail -match "package smoke import ok")) { 0 } else { 1 })
}

Remove-Item Env:\LOCAL_VOICE_DICTATION_SMOKE_IMPORT -ErrorAction SilentlyContinue
Copy-Item -LiteralPath (Join-Path $Root "voice_dictation_config.json") -Destination (Join-Path $testRoot "voice_dictation_config.json")
Copy-ModelsAsHardLinks -SourceModels (Join-Path $Root "models") -TargetModels (Join-Path $testRoot "models")

$process = Start-Process -FilePath $Exe -PassThru -WindowStyle Hidden
$ready = $false
$loadError = $false
$exitedEarly = $false

try {
    for ($i = 0; $i -lt $WaitForReadySeconds; $i++) {
        Start-Sleep -Seconds 1
        if ($process.HasExited) {
            $exitedEarly = $true
            break
        }
        $tail = Get-LogTail -LogPath $logPath -Lines 160
        if ($tail -match "load ready") {
            $ready = $true
            break
        }
        if ($tail -match "load error") {
            $loadError = $true
            break
        }
    }
} finally {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
}

[PSCustomObject]@{
    test_root = $testRoot
    mode = "full-load"
    process_id = $process.Id
    exited_early = $exitedEarly
    load_ready = $ready
    load_error = $loadError
    log_exists = Test-Path $logPath
    passed = ($ready -and -not $loadError -and -not $exitedEarly)
}
Get-LogTail -LogPath $logPath -Lines 120

exit $(if ($ready -and -not $loadError -and -not $exitedEarly) { 0 } else { 1 })
