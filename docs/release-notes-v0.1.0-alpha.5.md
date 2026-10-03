# NPU Dictate 0.1.0-alpha.5 Release Notes

Unsigned Windows pre-release for technical testing. Speech recognition still
targets Russian; the interface supports English and Russian. Intel NPU profiles
and CPU fallback remain available. Model weights are downloaded separately.

## Changes Since Alpha.4

- Long punctuation input uses overlapping, token-budgeted windows, preserving
  whole words and order without turning window boundaries into paragraphs.
- Automatic paste stops when target restoration fails or the input identity
  changes. Text remains available for manual recovery.
- Punctuation failure retains raw recognized text without automatically pasting
  or sending it. Empty and unusable punctuation results take the same fallback.
- Settings cannot replace an active recording's model/audio configuration.
  Recording indicators survive background loading events.
- Model settings show full progress, refresh installed labels and expose a safe
  idle-only retry. Old-generation progress/completion events are discarded.
- Empty/incomplete model files and malformed cached artifact metadata are not
  reported as ready. Invalid source metadata can be refreshed; converted artifact
  preparation retains size and SHA256 verification.
- Named modifier aliases match runtime keys; conflicting shortcuts are rejected.
- Failed settings saves remain recoverable. Default and unavailable microphone
  selections are preserved rather than silently selecting a different device.
- Settings fit individual monitor workareas with width-bound layouts. Small wheel
  events accumulate, and stop-without-Enter has native settings/menu commands.
- Russian loading metrics and opacity wording are corrected. Default copied
  diagnostics exclude dictated text, log tails and local paths.
- MSI ProductVersion is 0.1.5; EXE/product version is 0.1.0-alpha.5.
- Packaging now rejects failed/stale builds, binds MSI input to a fresh build
  receipt and inventories full ZIP/MSI payloads to exclude private app data.

## Verification Scope

The source remediation passed 69 isolated headless tests, 25 baseline smoke
groups and independent frozen-source reviews. The baseline has four expected
warnings for absent sandbox models/manifest and the skipped real CPU punctuation
test. These are not 94 unique tests because coverage overlaps.

Release package checks and publication evidence are recorded in
`docs/release-checklist-v0.1.0-alpha.5.md`. Do not infer a new model benchmark,
live paste/input test, installed-upgrade test or visual acceptance from the source
tests. ASR inference/buckets are unchanged from alpha.4; the long-punctuation
change and UI/runtime safeguards are included in this build.

## Known Limitations

- Unsigned prerelease: Windows may warn about an unknown publisher.
- First model download and cold OpenVINO/NPU compilation can be slow.
- Mixed-DPI rendering, negative-coordinate monitor transitions, real tray
  recovery and screen-reader behavior still need live acceptance on more systems.
- CPU/GPU availability depends on model profiles and detected hardware. GPU
  inference is not newly certified by this release.
- No new installed alpha.4-to-alpha.5 upgrade or private-audio regression is
  claimed without the corresponding release evidence.
- Resumable downloads, stable USB microphone identity and native accessibility
  of the Canvas overlay remain future work.

Portable ZIP and MSI do not include user configuration, logs, recordings, model
weights or Hugging Face credentials. Signing is not claimed.
