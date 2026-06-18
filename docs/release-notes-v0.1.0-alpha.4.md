# NPU Dictate 0.1.0-alpha.4 Release Notes

Status: unsigned public pre-release refresh while SignPath Foundation signing is pending.

## Summary

NPU Dictate 0.1.0-alpha.4 keeps the same local Russian dictation pipeline and focuses on startup reliability after first-run model setup.

This alpha is meant for technical users who are comfortable with unsigned Windows pre-release software or running a Python project from source.

## Changes Since 0.1.0-alpha.3

- Marks the app ready after ASR and microphone initialization instead of blocking startup on punctuation import and load.
- Loads the punctuation model in the background when punctuation is enabled.
- Waits for the same background punctuation load on the first dictation if it has not finished yet, avoiding duplicate punctuation loaders.
- Skips ASR warmup on NPU to avoid startup hangs seen during NPU bucket compilation.
- Keeps CPU ASR warmup behavior available for non-NPU profiles.
- Adds a smoke check that verifies NPU ASR warmup is skipped.

## Startup Notes

The overlay can become ready before punctuation has finished loading. In that case, the first dictation may wait briefly before punctuation is applied.

On the local NPU test machine, a repeated headless startup reached `Ready` in about 1.9 seconds after this change, while punctuation finished in the background about 11 seconds after launch. Cold OpenVINO/NPU startup can still be slower.

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
- Packaged app and MSI artifacts are unsigned until the SignPath Foundation flow is approved and configured.

## Suggested Pre-Release Checklist

- Run `tools/smoke_checks.py`.
- Run `tools/doctor.py`.
- Smoke-check packaged app import.
- Smoke-check MSI administrative extraction.
