param(
    [string]$Version = "0.1.0",
    [string]$Configuration = "alpha.5",
    [string]$ProductVersion = "",
    [switch]$SkipExeBuild
)

$ErrorActionPreference = "Stop"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$AppName = "NPU Dictate"
$AppId = "NPUDictate"
$Manufacturer = "Zoomerland"
$UpgradeCode = "EF3E8984-DA8E-4615-BD86-ACE089338FB3"
$DistDir = Join-Path $Root "dist\NPUDictate"
$ExePath = Join-Path $DistDir "NPUDictate.exe"
$IconPath = Join-Path $Root "assets\app-icon.ico"
$LicenseRtfPath = Join-Path $Root "packaging\license.rtf"
$InstallerDir = Join-Path $Root "dist\installer"
$IntermediateDir = Join-Path $Root "build\msi"
$WxsPath = Join-Path $IntermediateDir "NPUDictate.generated.wxs"
$MsiPath = Join-Path $InstallerDir "NPUDictate-$Version-$Configuration.msi"

if ([string]::IsNullOrWhiteSpace($ProductVersion)) {
    $versionParts = $Version.Split(".")
    if ($versionParts.Count -eq 3 -and $Configuration -match "^alpha\.(\d+)$") {
        $ProductVersion = [string]::Join(".", @($versionParts[0], $versionParts[1], $Matches[1]))
    } else {
        $ProductVersion = $Version
    }
}
if ($ProductVersion -notmatch "^\d+\.\d+\.\d+$") {
    throw "MSI ProductVersion must be a numeric three-part version: $ProductVersion"
}

function ConvertTo-WixId {
    param([string]$Prefix, [string]$Value)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Value))
    } finally {
        $sha.Dispose()
    }
    $hex = -join ($hash[0..7] | ForEach-Object { $_.ToString("x2") })
    $clean = ($Value -replace "[^A-Za-z0-9_.]", "_").Trim("_")
    if ($clean.Length -gt 40) {
        $clean = $clean.Substring(0, 40)
    }
    if ([string]::IsNullOrWhiteSpace($clean)) {
        $clean = "item"
    }
    return "${Prefix}_${clean}_$hex"
}

function ConvertTo-XmlAttribute {
    param([string]$Value)
    return [System.Security.SecurityElement]::Escape($Value)
}

function Get-RelativePath {
    param([string]$BasePath, [string]$Path)
    $baseFull = [System.IO.Path]::GetFullPath($BasePath)
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if ($baseFull.TrimEnd("\", "/") -ieq $pathFull.TrimEnd("\", "/")) {
        return ""
    }
    if (-not $baseFull.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $baseFull += [System.IO.Path]::DirectorySeparatorChar
    }
    $baseUri = [System.Uri]::new($baseFull)
    $pathUri = [System.Uri]::new($pathFull)
    $relativeUri = $baseUri.MakeRelativeUri($pathUri)
    return [System.Uri]::UnescapeDataString($relativeUri.ToString()).Replace("/", "\")
}

if (-not $SkipExeBuild) {
    & (Join-Path $Root "tools\build_windows_exe.ps1") -Clean -SkipInstall
    if ($LASTEXITCODE -ne 0) { throw "EXE build failed; MSI was not created." }
}

if (-not (Test-Path $ExePath)) {
    throw "Packaged executable not found: $ExePath"
}
if (-not (Test-Path $IconPath)) {
    throw "Application icon not found: $IconPath"
}
if (-not (Test-Path $LicenseRtfPath)) {
    throw "Installer license file not found: $LicenseRtfPath"
}

$ReceiptPath = Join-Path $Root "build\NPUDictate.build.json"
$InventoryPath = Join-Path $Root "build\NPUDictate.payload.json"
$Receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
$SourceCommit = git -C $Root rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $Receipt.source_commit -ne $SourceCommit) { throw "EXE receipt does not match the current source commit." }
$SourceStatus = git -C $Root status --porcelain
if ($LASTEXITCODE -ne 0 -or $SourceStatus) { throw "MSI build requires a clean source worktree." }
if ($Receipt.version -ne "$Version-$Configuration" -or (Get-Item -LiteralPath $ExePath).VersionInfo.ProductVersion -ne "$Version-$Configuration") {
    throw "EXE version does not match intended MSI version."
}
if ((Get-FileHash -LiteralPath $ExePath -Algorithm SHA256).Hash -ne $Receipt.exe_sha256 -or
    (Get-FileHash -LiteralPath $InventoryPath -Algorithm SHA256).Hash -ne $Receipt.inventory_sha256) {
    throw "EXE or payload inventory differs from the accepted build."
}
& (Join-Path $Root ".venv\Scripts\python.exe") -B (Join-Path $Root "tools\release_payload.py") --app-dir $DistDir --compare $InventoryPath
if ($LASTEXITCODE -ne 0) { throw "MSI payload differs from the accepted build." }

$toolList = dotnet tool list --local
if ($LASTEXITCODE -ne 0 -or -not ($toolList -match "wix\s+5\.")) {
    throw "WiX 5 local tool is not installed. Run: dotnet tool install wix --version 5.0.2"
}

$extensionList = dotnet wix extension list
if ($LASTEXITCODE -ne 0 -or -not ($extensionList -match "WixToolset\.UI\.wixext\s+5\.")) {
    dotnet wix extension add WixToolset.UI.wixext/5.0.2
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to add WiX UI extension."
    }
}

New-Item -ItemType Directory -Path $InstallerDir -Force | Out-Null
$IntermediateDir = [IO.Path]::GetFullPath($IntermediateDir)
$WorkspacePrefix = [IO.Path]::GetFullPath([string]$Root).TrimEnd("\", "/") + [IO.Path]::DirectorySeparatorChar
if (-not $IntermediateDir.StartsWith($WorkspacePrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "MSI intermediate directory escapes workspace."
}
if (Test-Path -LiteralPath $IntermediateDir) { Remove-Item -LiteralPath $IntermediateDir -Recurse -Force -ErrorAction Stop }
New-Item -ItemType Directory -Path $IntermediateDir -Force | Out-Null

$directories = @{}
$directories[""] = "INSTALLFOLDER"
$allDirs = Get-ChildItem -LiteralPath $DistDir -Recurse -Directory | Sort-Object FullName
foreach ($dir in $allDirs) {
    $relative = Get-RelativePath -BasePath $DistDir -Path $dir.FullName
    $directories[$relative] = ConvertTo-WixId -Prefix "DIR" -Value $relative
}

$files = Get-ChildItem -LiteralPath $DistDir -Recurse -File | Sort-Object FullName
$directoryChildren = @{}
foreach ($dir in $allDirs) {
    $parentRelative = Get-RelativePath -BasePath $DistDir -Path $dir.Parent.FullName
    if ($parentRelative -eq ".") {
        $parentRelative = ""
    }
    if (-not $directoryChildren.ContainsKey($parentRelative)) {
        $directoryChildren[$parentRelative] = @()
    }
    $directoryChildren[$parentRelative] += $dir
}

function Write-DirectoryTree {
    param(
        [System.Text.StringBuilder]$Builder,
        [string]$RelativePath,
        [int]$Indent
    )
    if (-not $directoryChildren.ContainsKey($RelativePath)) {
        return
    }
    $prefix = " " * $Indent
    foreach ($child in $directoryChildren[$RelativePath]) {
        $childRelative = Get-RelativePath -BasePath $DistDir -Path $child.FullName
        $id = $directories[$childRelative]
        $name = ConvertTo-XmlAttribute $child.Name
        [void]$Builder.AppendLine("$prefix<Directory Id=`"$id`" Name=`"$name`">")
        Write-DirectoryTree -Builder $Builder -RelativePath $childRelative -Indent ($Indent + 2)
        [void]$Builder.AppendLine("$prefix</Directory>")
    }
}

$directoryXml = [System.Text.StringBuilder]::new()
Write-DirectoryTree -Builder $directoryXml -RelativePath "" -Indent 10

$componentsXml = [System.Text.StringBuilder]::new()
$index = 0
foreach ($file in $files) {
    $index += 1
    $relative = Get-RelativePath -BasePath $DistDir -Path $file.FullName
    $dirRelative = Split-Path -Parent $relative
    if ($dirRelative -eq ".") {
        $dirRelative = ""
    }
    $dirId = $directories[$dirRelative]
    $componentId = ConvertTo-WixId -Prefix "CMP" -Value $relative
    $fileId = ConvertTo-WixId -Prefix "FIL" -Value $relative
    $source = ConvertTo-XmlAttribute $file.FullName
    [void]$componentsXml.AppendLine("    <Component Id=`"$componentId`" Directory=`"$dirId`" Guid=`"*`">")
    [void]$componentsXml.AppendLine("      <File Id=`"$fileId`" Source=`"$source`" KeyPath=`"yes`" />")
    [void]$componentsXml.AppendLine("    </Component>")
}

$wxs = @"
<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs" xmlns:ui="http://wixtoolset.org/schemas/v4/wxs/ui">
  <Package
    Name="$AppName"
    Manufacturer="$Manufacturer"
    Version="$ProductVersion"
    UpgradeCode="$UpgradeCode"
    Scope="perUser"
    Language="1033">

    <MajorUpgrade DowngradeErrorMessage="A newer version of $AppName is already installed." />
    <MediaTemplate EmbedCab="yes" CompressionLevel="high" />
    <Icon Id="AppIcon.ico" SourceFile="$(ConvertTo-XmlAttribute $IconPath)" />
    <Property Id="ARPPRODUCTICON" Value="AppIcon.ico" />
    <WixVariable Id="WixUILicenseRtf" Value="$(ConvertTo-XmlAttribute $LicenseRtfPath)" />
    <ui:WixUI Id="WixUI_Minimal" />
    <UIRef Id="WixUI_ErrorProgressText" />

    <StandardDirectory Id="LocalAppDataFolder">
      <Directory Id="INSTALLFOLDER" Name="$AppId">
$directoryXml      </Directory>
    </StandardDirectory>

    <StandardDirectory Id="ProgramMenuFolder">
      <Directory Id="ApplicationProgramsFolder" Name="$AppName" />
    </StandardDirectory>

    <ComponentGroup Id="AppFiles">
$componentsXml    </ComponentGroup>

    <Component Id="ApplicationShortcut" Directory="ApplicationProgramsFolder" Guid="*">
      <Shortcut
        Id="ApplicationStartMenuShortcut"
        Name="$AppName"
        Description="Local offline NPU-first voice dictation"
        Target="[INSTALLFOLDER]NPUDictate.exe"
        WorkingDirectory="INSTALLFOLDER"
        Icon="AppIcon.ico" />
      <RemoveFolder Id="RemoveApplicationProgramsFolder" On="uninstall" />
      <RegistryValue
        Root="HKCU"
        Key="Software\$Manufacturer\$AppId"
        Name="installed"
        Type="integer"
        Value="1"
        KeyPath="yes" />
    </Component>

    <Feature Id="MainFeature" Title="$AppName" Level="1">
      <ComponentGroupRef Id="AppFiles" />
      <ComponentRef Id="ApplicationShortcut" />
    </Feature>
  </Package>
</Wix>
"@

Set-Content -LiteralPath $WxsPath -Value $wxs -Encoding UTF8

dotnet wix build $WxsPath -ext WixToolset.UI.wixext -arch x64 -out $MsiPath -intermediatefolder $IntermediateDir
if ($LASTEXITCODE -ne 0) {
    throw "WiX MSI build failed."
}

if (-not (Test-Path $MsiPath)) {
    throw "MSI build finished but output was not found: $MsiPath"
}

Write-Host "Built $MsiPath"
Write-Host "MSI ProductVersion: $ProductVersion"
