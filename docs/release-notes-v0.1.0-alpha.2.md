# NPU Dictate 0.1.0-alpha.2 Release Notes

Status: unsigned public pre-release refresh while SignPath Foundation signing is pending.

## Summary

NPU Dictate 0.1.0-alpha.2 keeps the same local Russian dictation pipeline as 0.1.0-alpha.1 and improves the first-run model setup experience.

This alpha is meant for technical users who are comfortable with unsigned Windows pre-release software or running a Python project from source.

## Changes Since 0.1.0-alpha.1

- Added clearer first-run model setup status before models are downloaded.
- Added visible download progress with percent, transferred size, remaining size, speed, ETA, and per-file labels.
- Added model status details in Settings: language, purpose, model-supported devices, current-PC available devices, and downloaded/missing state.
- Made the Russian-only dictation scope explicit in Settings.
- Routed direct ASR model downloads through the app downloader so CPU/FP32 downloads are no longer silent.
- Kept model weights and converted OpenVINO artifacts outside the installer.

## Distribution Policy For 0.1.0-alpha.2

0.1.0-alpha.2 may publish unsigned Windows artifacts while code signing is pending:

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
- First converted-artifact download requires internet access and about 566 MB of model files.
- Packaged app and MSI artifacts are unsigned until the SignPath Foundation flow is approved and configured.

## Suggested Pre-Release Checklist

- Run `tools/smoke_checks.py`.
- Run `tools/doctor.py`.
- Smoke-check packaged app import.
- Smoke-check MSI administrative extraction.
