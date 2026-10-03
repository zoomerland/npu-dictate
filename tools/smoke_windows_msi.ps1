param(
    [string]$MsiPath = "",
    [string]$ExpectedProductVersion = "",
    [string]$ExpectedExeVersion = "0.1.0-alpha.5",
    [string]$InventoryPath = ""
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
if ([string]::IsNullOrWhiteSpace($MsiPath)) {
    $MsiPath = Join-Path $Root "dist\installer\NPUDictate-0.1.0-alpha.5.msi"
}
$MsiPath = (Resolve-Path $MsiPath).Path
if ([string]::IsNullOrWhiteSpace($InventoryPath)) {
    $InventoryPath = Join-Path $Root "build\NPUDictate.payload.json"
}
$InventoryPath = (Resolve-Path -LiteralPath $InventoryPath).Path

function Get-MsiProperty {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $installer = New-Object -ComObject WindowsInstaller.Installer
    $database = $null
    $view = $null
    $record = $null
    try {
        $database = $installer.GetType().InvokeMember(
            "OpenDatabase",
            [System.Reflection.BindingFlags]::InvokeMethod,
            $null,
            $installer,
            @($Path, 0)
        )
        $query = "SELECT ``Value`` FROM ``Property`` WHERE ``Property``='$Name'"
        $view = $database.GetType().InvokeMember(
            "OpenView",
            [System.Reflection.BindingFlags]::InvokeMethod,
            $null,
            $database,
            @($query)
        )
        $view.GetType().InvokeMember(
            "Execute",
            [System.Reflection.BindingFlags]::InvokeMethod,
            $null,
            $view,
            $null
        ) | Out-Null
        $record = $view.GetType().InvokeMember(
            "Fetch",
            [System.Reflection.BindingFlags]::InvokeMethod,
            $null,
            $view,
            $null
        )
        if ($null -eq $record) {
            return $null
        }
        return $record.GetType().InvokeMember(
            "StringData",
            [System.Reflection.BindingFlags]::GetProperty,
            $null,
            $record,
            @(1)
        )
    } finally {
        foreach ($item in @($record, $view, $database, $installer)) {
            if ($null -ne $item -and [System.Runtime.InteropServices.Marshal]::IsComObject($item)) {
                [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($item)
            }
        }
    }
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Target = Join-Path $env:TEMP "lvd-msi-admin-$Stamp"
$Log = Join-Path $env:TEMP "lvd-msi-admin-$Stamp.log"
New-Item -ItemType Directory -Path $Target | Out-Null

$ArgString = "/a `"$MsiPath`" /qn TARGETDIR=`"$Target`" /L*v `"$Log`""
$Process = Start-Process -FilePath msiexec.exe -ArgumentList $ArgString -PassThru -WindowStyle Hidden
try {
    if (-not $Process.WaitForExit(300000)) { throw "MSI administrative extraction timed out." }
} finally {
    if (-not $Process.HasExited) { Stop-Process -Id $Process.Id -Force }
}
$InstallRoot = Join-Path $Target "LocalApp\NPUDictate"
$ExePath = Join-Path $InstallRoot "NPUDictate.exe"
$AppModelsPath = Join-Path $InstallRoot "models"
$ProductVersion = Get-MsiProperty -Path $MsiPath -Name "ProductVersion"
$FileCount = (Get-ChildItem -LiteralPath $Target -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
$ExeProductVersion = if (Test-Path -LiteralPath $ExePath) { (Get-Item -LiteralPath $ExePath).VersionInfo.ProductVersion } else { "" }
$Passed = (
    $Process.ExitCode -eq 0 `
    -and (Test-Path $ExePath) `
    -and -not (Test-Path $AppModelsPath) `
    -and (
        [string]::IsNullOrWhiteSpace($ExpectedProductVersion) `
        -or $ProductVersion -eq $ExpectedProductVersion
    ) `
    -and $FileCount -gt 0 `
    -and $ExeProductVersion -eq $ExpectedExeVersion
)

if ($Passed) {
    & (Join-Path $Root ".venv\Scripts\python.exe") -B (Join-Path $Root "tools\release_payload.py") --app-dir $InstallRoot --compare $InventoryPath
    if ($LASTEXITCODE -ne 0) { $Passed = $false }
}
if ($Passed) {
    & (Join-Path $Root "tools\smoke_packaged_exe.ps1") -ImportOnly -ExePath $ExePath
    if ($LASTEXITCODE -ne 0) { $Passed = $false }
}

[PSCustomObject]@{
    msi = $MsiPath
    exit_code = $Process.ExitCode
    target = $Target
    log = $Log
    install_root = $InstallRoot
    exe_exists = Test-Path $ExePath
    app_local_models_exists = Test-Path $AppModelsPath
    product_version = $ProductVersion
    expected_product_version = $ExpectedProductVersion
    file_count = $FileCount
    passed = $Passed
}

exit $(if ($Passed) { 0 } else { 1 })
