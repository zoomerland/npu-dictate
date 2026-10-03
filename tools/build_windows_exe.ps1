param(
    [switch]$Clean,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Spec = Join-Path $Root "packaging\npu_dictate.spec"
$Receipt = Join-Path $Root "build\NPUDictate.build.json"
$Inventory = Join-Path $Root "build\NPUDictate.payload.json"
$PayloadCheck = Join-Path $Root "tools\release_payload.py"

if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found: $Python"
}

if (Test-Path -LiteralPath $Receipt) { Remove-Item -LiteralPath $Receipt -Force -ErrorAction Stop }
$SourceCommit = git -C $Root rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw "Cannot determine build source commit." }
$SourceStatus = git -C $Root status --porcelain
if ($LASTEXITCODE -ne 0 -or $SourceStatus) { throw "Build requires a clean source worktree." }

if (-not $SkipInstall) {
    & $Python -m pip install -r (Join-Path $Root "requirements-dev.txt")
    if ($LASTEXITCODE -ne 0) { throw "Build dependency installation failed." }
}

if ($Clean) {
    foreach ($Relative in @("build\npu_dictate", "dist\NPUDictate")) {
        $Target = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
        $WorkspacePrefix = [IO.Path]::GetFullPath([string]$Root).TrimEnd("\", "/") + [IO.Path]::DirectorySeparatorChar
        if (-not $Target.StartsWith($WorkspacePrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Cleanup target escapes workspace: $Target"
        }
        if (Test-Path -LiteralPath $Target) {
            if ($Relative -eq "dist\NPUDictate") {
                & $Python -B $PayloadCheck --app-dir $Target
                if ($LASTEXITCODE -ne 0) { throw "Existing output contains unapproved data; preserve it before rebuilding." }
            }
            Remove-Item -LiteralPath $Target -Recurse -Force -ErrorAction Stop
        }
    }
}

& $Python -m PyInstaller --noconfirm --clean $Spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$Exe = Join-Path $Root "dist\NPUDictate\NPUDictate.exe"
if (-not (Test-Path $Exe)) {
    throw "Build finished but executable was not found: $Exe"
}

& $Python -B $PayloadCheck --app-dir (Split-Path -Parent $Exe) --inventory-out $Inventory
if ($LASTEXITCODE -ne 0) { throw "Fresh EXE payload validation failed." }
$FinalCommit = git -C $Root rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $FinalCommit -ne $SourceCommit) { throw "Source commit changed during the build." }
$FinalStatus = git -C $Root status --porcelain
if ($LASTEXITCODE -ne 0 -or $FinalStatus) { throw "Source worktree changed during the build." }
@{
    source_commit = $SourceCommit
    exe_sha256 = (Get-FileHash -LiteralPath $Exe -Algorithm SHA256).Hash
    inventory_sha256 = (Get-FileHash -LiteralPath $Inventory -Algorithm SHA256).Hash
    version = (Get-Item -LiteralPath $Exe).VersionInfo.ProductVersion
} | ConvertTo-Json | Set-Content -LiteralPath $Receipt -Encoding utf8

Write-Host "Built $Exe"
