"""Synthetic payload and native-build failure regressions; no actual build/install."""
import json
import base64
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from release_payload import checked_path, inventory


class PayloadTests(unittest.TestCase):
    def test_public_resources_and_runtime_libraries_are_allowed(self):
        for name in ("NPUDictate.exe", "_internal/voice_dictation_config.example.json",
                     "_internal/openvino/libs/cache.json", "_internal/torch/lib/cpu.bin",
                     "_internal/transformers/models/auto/config.json", "_internal/onnx_asr/models/vocab.txt"):
            self.assertEqual(checked_path(name), name)

    def test_private_data_and_app_weights_are_rejected_at_any_depth(self):
        for suffix in ("voice_dictation_config.json", "voice_dictation_config.json.bak",
                       "voice_dictation.log", ".hf/token", "recordings/test.wav",
                       "models/weights.bin", ".manifests/MANIFEST.json", "hf_export/model.bin",
                       "v3_ctc.int8.onnx", "v3_ctc_bucket400.bin", "openvino_model.xml"):
            for prefix in ("", "_internal/user/"):
                with self.subTest(path=prefix + suffix), self.assertRaises(ValueError):
                    checked_path(prefix + suffix)

    def test_path_traversal_is_rejected(self):
        for name in ("../outside", "/absolute", "C:/outside", "_internal/../secret"):
            with self.assertRaises(ValueError):
                checked_path(name)

    def test_folder_and_zip_have_identical_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "app"
            root.mkdir()
            (root / "NPUDictate.exe").write_bytes(b"synthetic exe")
            (root / "README.md").write_bytes(b"public docs")
            zipped = Path(temp) / "app.zip"
            with zipfile.ZipFile(zipped, "w") as archive:
                for path in root.iterdir():
                    archive.write(path, path.name)
            self.assertEqual(inventory(app_dir=root), inventory(archive=zipped))

    def test_contaminated_and_duplicate_zip_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for name in ("nested/recordings/audio.wav", "NPUDICTATE.exe"):
                zipped = Path(temp) / "bad.zip"
                with zipfile.ZipFile(zipped, "w") as archive:
                    archive.writestr("NPUDictate.exe", b"exe")
                    archive.writestr(name, b"extra")
                with self.assertRaises(ValueError):
                    inventory(archive=zipped)

    def test_missing_exe_and_contaminated_folder_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                inventory(app_dir=root)
            (root / "NPUDictate.exe").write_bytes(b"exe")
            (root / "voice_dictation_config.json").write_bytes(b"private synthetic")
            with self.assertRaises(ValueError):
                inventory(app_dir=root)


HARNESS = r'''
$ErrorActionPreference = 'Stop'
$root = $env:SYNTHETIC_ROOT
$PSScriptRoot = Join-Path $root 'tools'
$case = $env:SYNTHETIC_CASE
function Resolve-Path { $env:SYNTHETIC_ROOT }
function git {
    $global:LASTEXITCODE = 0
    if ($args -contains 'status') { if ($case -eq 'dirty') { ' M synthetic.py' } }
    else { 'a' * 40 }
}
function Invoke-FakePython {
    $global:LASTEXITCODE = if ($args -contains 'pip') { 9 } elseif ($args -contains 'PyInstaller') { 17 } else { 0 }
}
function Invoke-FakeBuild { $global:LASTEXITCODE = 17 }
function Remove-Item {
    param($LiteralPath, [switch]$Force, [switch]$Recurse, $ErrorAction)
    if ($case -eq 'cleanup' -and $Recurse) { throw 'Synthetic cleanup denied' }
    Microsoft.PowerShell.Management\Remove-Item -LiteralPath $LiteralPath -Force:$Force -Recurse:$Recurse -ErrorAction $ErrorAction
}
function Get-Item { [pscustomobject]@{VersionInfo=[pscustomobject]@{ProductVersion='0.1.0-alpha.5'}} }
$source = Get-Content -LiteralPath $env:SYNTHETIC_SCRIPT -Raw
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Harness source parse failed' }
$calls = $ast.FindAll({param($n) $n -is [System.Management.Automation.Language.CommandAst] -and $n.InvocationOperator -eq 'Ampersand'}, $true)
foreach ($call in ($calls | Sort-Object {$_.Extent.StartOffset} -Descending)) {
    if ($call.CommandElements[0].Extent.Text -eq '$Python') {
        $replacement = 'Invoke-FakePython ' + (($call.CommandElements | Select-Object -Skip 1 | ForEach-Object {$_.Extent.Text}) -join ' ')
    } elseif ($call.Extent.Text -match 'build_windows_exe.ps1') { $replacement = 'Invoke-FakeBuild' }
    else { continue }
    $source = $source.Remove($call.Extent.StartOffset, $call.Extent.EndOffset - $call.Extent.StartOffset).Insert($call.Extent.StartOffset, $replacement)
}
$ast = [System.Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$errors)
$roots = $ast.FindAll({param($n) $n -is [System.Management.Automation.Language.VariableExpressionAst] -and $n.VariablePath.UserPath -eq 'PSScriptRoot'}, $true)
foreach ($node in ($roots | Sort-Object {$_.Extent.StartOffset} -Descending)) {
    $source = $source.Remove($node.Extent.StartOffset, $node.Extent.EndOffset - $node.Extent.StartOffset).Insert($node.Extent.StartOffset, '$env:SYNTHETIC_TOOLS_ROOT')
}
$script = [scriptblock]::Create($source)
try {
    if ($case -eq 'cleanup') { & $script -Clean -SkipInstall }
    elseif ($case -eq 'pip') { & $script }
    elseif ($case -like 'receipt-*') { & $script -SkipExeBuild }
    elseif ($case -eq 'child') { & $script }
    else { & $script -SkipInstall }
    throw 'Harness unexpectedly accepted failure'
} catch {
    if ($_.Exception.Message -like '*unexpectedly accepted*') { throw }
    Write-Output ('REJECTED: ' + $_.Exception.Message)
}
'''


class BuildGuardTests(unittest.TestCase):
    def run_case(self, case, expected):
        with tempfile.TemporaryDirectory(prefix="npu-build-guard-") as temp:
            root = Path(temp)
            for name in (".venv/Scripts/python.exe", "dist/NPUDictate/NPUDictate.exe",
                         "assets/app-icon.ico", "packaging/license.rtf", "build/NPUDictate.payload.json"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"synthetic stale/partial output")
            (root / "build/npu_dictate").mkdir()
            receipt = dict(source_commit="a" * 40, version="0.1.0-alpha.5", exe_sha256="bad", inventory_sha256="bad")
            if case == "receipt-source":
                receipt["source_commit"] = "b" * 40
            if case == "receipt-version":
                receipt["version"] = "0.1.0-alpha.4"
            (root / "build/NPUDictate.build.json").write_text(json.dumps(receipt), encoding="utf-8")
            script = "build_windows_msi.ps1" if case.startswith("receipt-") or case == "child" else "build_windows_exe.ps1"
            env = dict(os.environ, SYNTHETIC_ROOT=temp, SYNTHETIC_CASE=case,
                       SYNTHETIC_TOOLS_ROOT=str(root / "tools"),
                       SYNTHETIC_SCRIPT=str(Path(__file__).parent / script))
            encoded = base64.b64encode(HARNESS.encode("utf-16-le")).decode("ascii")
            result = subprocess.run([shutil.which("pwsh") or "pwsh", "-NoProfile", "-EncodedCommand", encoded],
                                    text=True, capture_output=True, env=env, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(expected, result.stdout)
            self.assertNotIn("Built ", result.stdout)

    def test_failed_native_builder_rejects_stale_partial_exe(self):
        self.run_case("builder", "PyInstaller build failed")

    def test_failed_dependency_install_is_not_accepted(self):
        self.run_case("pip", "dependency installation failed")

    def test_failed_cleanup_is_not_ignored(self):
        self.run_case("cleanup", "Synthetic cleanup denied")

    def test_dirty_source_is_not_certified(self):
        self.run_case("dirty", "clean source worktree")

    def test_failed_child_builder_cannot_enter_msi_harvesting(self):
        self.run_case("child", "EXE build failed; MSI was not created")

    def test_source_receipt_mismatch_is_not_accepted(self):
        self.run_case("receipt-source", "does not match the current source commit")

    def test_version_receipt_mismatch_is_not_accepted(self):
        self.run_case("receipt-version", "EXE version does not match")

    def test_payload_hash_mismatch_is_not_accepted(self):
        self.run_case("receipt-hash", "differs from the accepted build")


if __name__ == "__main__":
    unittest.main(verbosity=2)
