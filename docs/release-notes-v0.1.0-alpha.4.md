# NPU Dictate 0.1.0-alpha.4 Release Notes

Status: unsigned public pre-release refresh while SignPath Foundation signing is pending.

## Summary

NPU Dictate 0.1.0-alpha.4 keeps the local Russian NPU-first dictation pipeline and focuses on safer everyday insertion, responsive startup/shutdown, and recoverable runtime behavior.

This alpha is meant for technical users who are comfortable with unsigned Windows pre-release software or running a Python project from source.

## Changes Since 0.1.0-alpha.3

- Adds optional automatic Enter after a successful paste, plus a secondary overlay stop button that keeps the text available for review without sending it.
- Guards automatic Enter with the active root window, Win32 focus window, and process identity. When exact UI Automation field identity is available, the field must also remain unchanged.
- Removes accidental punctuation at the beginning of genuinely empty input while preserving meaningful punctuation when dictation continues existing text.
- Makes every settings section scrollable on smaller or scaled displays.
- Marks the app ready after ASR and microphone initialization instead of blocking startup on punctuation import and load.
- Loads the punctuation model in the background when punctuation is enabled.
- Waits for the same background punctuation load on the first dictation if it has not finished yet, avoiding duplicate punctuation loaders.
- Skips ASR warmup on NPU to avoid startup hangs seen during NPU bucket compilation.
- Keeps CPU ASR warmup behavior available for non-NPU profiles.
- Makes recording handoff atomic and lets normal shutdown wait for an active transcription instead of losing it.
- Discards stale ASR, punctuation, and status generations after settings change.
- Serializes audio stream replacement while keeping PortAudio start/stop work off the Tk UI thread.
- Coalesces overlapping audio restart requests so the latest input-device configuration wins.
- Makes microphone discovery and single-instance initialization failures visible and recoverable.
- Writes configuration atomically with recovery from invalid JSON.
- Rejects incomplete direct model downloads using the expected size or `Content-Length`.
- Separates install and user-data roots for packaged tests and future layouts while preserving the existing portable default.
- Gives alpha.4 the numeric MSI `ProductVersion` `0.1.4`, allowing Windows Installer to distinguish it from earlier `0.1.0` alpha packages.

## Startup Notes

The overlay can become ready before punctuation has finished loading. In that case, the first dictation may wait briefly before punctuation is applied.

On the local NPU test machine, repeated startup can reach `Ready` in about 2 seconds, while a clean OpenVINO/NPU load can take about 10 seconds and punctuation may finish later in the background. First compilation and cold filesystem caches can be slower.

## Verification

- Full developer smoke suite: 0 failures and 0 warnings.
- Strict doctor: 24 OK, 0 warnings, 0 failures.
- Saved-audio regression: 8 real recordings, 61.61 seconds total, no empty results or runtime errors.
- On that corpus, NPU NNCF INT8 b400 took 2.323 seconds versus 14.689 seconds for CPU ONNX INT8, a 6.32x processing-time advantage on the test laptop.
- Independent runtime and Enter-target reviews completed without actionable findings.
- Packaged import, full model load, MSI extraction, and installer upgrade checks are release gates.

## Distribution Policy For 0.1.0-alpha.4

0.1.0-alpha.4 may publish unsigned Windows artifacts while code signing is pending:

- Publish source code.
- Publish setup instructions.
- Publish model download/conversion code.
- Download current converted OpenVINO artifacts from `Zoomerland/local-voice-dictation-openvino` at first setup.
- Publish the unsigned packaged app archive and MSI for technical testing.
- Clearly label packaged artifacts as unsigned pre-release builds.
- Do not bundle model weights or converted OpenVINO artifacts.

Code signing remains pending through the SignPath Foundation application.

## Known Limitations

- Russian speech recognition is the current focus.
- UI language is independent from speech recognition language. English/Russian UI does not imply English ASR support.
- User-provided custom models are out of scope for v0.1.
- GPU profiles are not considered tested yet.
- First model preparation and first OpenVINO/NPU compilation can be slow.
- Exact focus-field identity is not exposed by every Windows application. In those cases automatic Enter falls back to checking the active window, Win32 focus window, and process.
- Packaged app and MSI artifacts are unsigned until the SignPath Foundation flow is approved and configured.

## Suggested Pre-Release Checklist

- Run `tools/smoke_checks.py --rupunct-timeout 120`.
- Run `tools/doctor.py --strict`.
- Smoke-check packaged app import.
- Smoke-check packaged full model load.
- Smoke-check MSI administrative extraction.
- Verify the MSI product version and alpha.3-to-alpha.4 upgrade path.
- Publish SHA256 checksums for every release asset.
