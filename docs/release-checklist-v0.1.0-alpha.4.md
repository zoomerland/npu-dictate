# NPU Dictate 0.1.0-alpha.4 Release Checklist

Status: published as an unsigned public pre-release on 2026-07-24.

## Identity

- App version: `0.1.0-alpha.4`.
- Git tag: `v0.1.0-alpha.4`.
- MSI ProductVersion: `0.1.4`.
- Target branch: `main`.
- Signing: pending SignPath Foundation approval; artifacts must be labeled unsigned.

## Intended Assets

- `NPUDictate-0.1.0-alpha.4-win-x64.zip`.
- `NPUDictate-0.1.0-alpha.4.msi`.
- `SHA256SUMS.txt`.

Model files, converted OpenVINO artifacts, user configuration, logs, and recordings must not be bundled or committed.

## Gates

- [x] Live dictation and guarded automatic Enter tested in Codex.
- [x] Saved-audio CPU/NPU regression completed.
- [x] Full source smoke suite completed with no failures or warnings.
- [x] Independent runtime and Enter-target reviews passed.
- [x] Strict doctor passes on the release branch: 24 OK, 0 warnings, 0 failures.
- [x] Release metadata and MSI version mapping validated.
- [x] Clean PyInstaller build succeeds.
- [x] Packaged import smoke passes.
- [x] Packaged full NPU model-load smoke passes.
- [x] MSI build reports ProductVersion `0.1.4`.
- [x] MSI administrative extraction smoke passes.
- [x] Alpha.3-to-alpha.4 install/upgrade smoke passes without removing user data.
- [x] Release archive and SHA256 checksums are generated.
- [x] Independent final release review passes.
- [x] Release branch is merged into `main`.
- [x] `main` is pushed and GitHub CI passes for tag `v0.1.0-alpha.4`.
- [x] CI-built artifacts match the intended names and pass checksum verification.
- [x] GitHub pre-release is created with release notes and all three assets.
- [x] Published MSI/ZIP download and final launch smoke pass.

## Local Artifact Evidence

Validated on 2026-07-24:

- Clean one-dir build: 5,817 files, 917,721,850 bytes.
- Packaged import smoke: passed.
- Packaged full-load smoke: NPU ASR ready without load errors.
- MSI administrative extraction: 5,818 files; no bundled app model weights or app-local model directory.
- Public alpha.3 upgraded in place to alpha.4 as one registered product.
- Installed MSI version: `0.1.4`; executable product version: `0.1.0-alpha.4`.
- All 17 existing model files remained byte-identical after upgrade.
- Existing configuration, backup configuration, and log remained byte-identical after upgrade.
- Installed alpha.4 full-load smoke: passed on NPU.

Local artifact checksums:

```text
7120c6b69381d354682649466781583da0bd8366df5e6ecb355bc602597602ed  NPUDictate-0.1.0-alpha.4-win-x64.zip
f5eb02e8d13522ec023cc93e3fe730535e08e10f768b6ae560ec3135b51f987a  NPUDictate-0.1.0-alpha.4.msi
```

These are local pre-tag build checksums. The published checksum file must be
regenerated from the CI-built artifacts.

## Published Artifact Evidence

- Release: <https://github.com/zoomerland/npu-dictate/releases/tag/v0.1.0-alpha.4>
- GitHub Actions run: <https://github.com/zoomerland/npu-dictate/actions/runs/30056027835>
- CI packaged import smoke: passed.
- CI MSI extraction smoke: passed with `ProductVersion=0.1.4`.
- Downloaded CI ZIP import and full NPU model-load smoke: passed.
- Fresh public downloads matched the published checksum file.
- The public MSI installed as one product with version `0.1.4`.
- Existing model and user files remained byte-identical.
- The installed public build reached `Ready` on NPU and was left running.

Published artifact checksums:

```text
bebc889bea63d239f0bcc452a415b0760ce023f46f0b3a67d36434c104004556  NPUDictate-0.1.0-alpha.4-win-x64.zip
1ec3acc9e7ba9cdf5eafbd5519f6cd1b470aac674a2041448a0648cf20ee1289  NPUDictate-0.1.0-alpha.4.msi
```
