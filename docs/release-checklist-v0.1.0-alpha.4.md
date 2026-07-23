# NPU Dictate 0.1.0-alpha.4 Release Checklist

Status: preparing an unsigned public pre-release.

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
- [ ] Release metadata and MSI version mapping validated.
- [ ] Clean PyInstaller build succeeds.
- [ ] Packaged import smoke passes.
- [ ] Packaged full NPU model-load smoke passes.
- [ ] MSI build reports ProductVersion `0.1.4`.
- [ ] MSI administrative extraction smoke passes.
- [ ] Alpha.3-to-alpha.4 install/upgrade smoke passes without removing user data.
- [ ] Release archive and SHA256 checksums are generated.
- [ ] Independent final release review passes.
- [ ] Release branch is merged into `main`.
- [ ] `main` is pushed and GitHub CI passes for tag `v0.1.0-alpha.4`.
- [ ] CI-built artifacts match the intended names and pass checksum verification.
- [ ] GitHub pre-release is created with release notes and all three assets.
- [ ] Published MSI/ZIP download and final launch smoke pass.
