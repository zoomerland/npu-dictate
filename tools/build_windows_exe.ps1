param(
    [switch]$Clean,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Spec = Join-Path $Root "packaging\local_voice_dictation.spec"

if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found: $Python"
}

if (-not $SkipInstall) {
    & $Python -m pip install -r (Join-Path $Root "requirements-dev.txt")
}

if ($Clean) {
    Remove-Item -LiteralPath (Join-Path $Root "build") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $Root "dist") -Recurse -Force -ErrorAction SilentlyContinue
}

& $Python -m PyInstaller --noconfirm --clean $Spec

$Exe = Join-Path $Root "dist\LocalVoiceDictation\LocalVoiceDictation.exe"
if (-not (Test-Path $Exe)) {
    throw "Build finished but executable was not found: $Exe"
}

Write-Host "Built $Exe"
