param(
    [string]$MsiPath = ""
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
if ([string]::IsNullOrWhiteSpace($MsiPath)) {
    $MsiPath = Join-Path $Root "dist\installer\NPUDictate-0.1.0-alpha.3.msi"
}
$MsiPath = (Resolve-Path $MsiPath).Path

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Target = Join-Path $env:TEMP "lvd-msi-admin-$Stamp"
$Log = Join-Path $env:TEMP "lvd-msi-admin-$Stamp.log"
New-Item -ItemType Directory -Path $Target | Out-Null

$ArgString = "/a `"$MsiPath`" /qn TARGETDIR=`"$Target`" /L*v `"$Log`""
$Process = Start-Process -FilePath msiexec.exe -ArgumentList $ArgString -Wait -PassThru
$InstallRoot = Join-Path $Target "LocalApp\NPUDictate"
$ExePath = Join-Path $InstallRoot "NPUDictate.exe"
$AppModelsPath = Join-Path $InstallRoot "models"
$FileCount = (Get-ChildItem -LiteralPath $Target -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
$Passed = (
    $Process.ExitCode -eq 0 `
    -and (Test-Path $ExePath) `
    -and -not (Test-Path $AppModelsPath) `
    -and $FileCount -gt 0
)

[PSCustomObject]@{
    msi = $MsiPath
    exit_code = $Process.ExitCode
    target = $Target
    log = $Log
    install_root = $InstallRoot
    exe_exists = Test-Path $ExePath
    app_local_models_exists = Test-Path $AppModelsPath
    file_count = $FileCount
    passed = $Passed
}

exit $(if ($Passed) { 0 } else { 1 })
