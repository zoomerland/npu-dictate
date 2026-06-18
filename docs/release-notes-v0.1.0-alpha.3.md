# NPU Dictate 0.1.0-alpha.3 Release Notes

Status: unsigned public pre-release refresh while SignPath Foundation signing is pending.

## Summary

NPU Dictate 0.1.0-alpha.3 keeps the same local Russian dictation pipeline and focuses on making setup states less confusing.

This alpha is meant for technical users who are comfortable with unsigned Windows pre-release software or running a Python project from source.

## Changes Since 0.1.0-alpha.2

- Shows real download percent directly on the overlay button when files are actively downloading.
- Uses a determinate overlay progress bar when download percent is known.
- Keeps long byte/speed/ETA download details in the status line, but compacts them so the overlay is readable.
- Replaces generic `BUSY` button text with clearer load-phase labels such as `LOAD`, `ASR`, `PUNCT`, and `WARM`.
- Adds a minimal MSI installer wizard with a completion page instead of a silent disappear-after-install flow.
- Keeps model weights and converted OpenVINO artifacts outside the installer.

## Important Setup Note

If the overlay is yellow but does not show a percent, the app is not downloading files. It is loading, compiling, or warming already-downloaded local models.

The first converted-artifact download requires internet access and about 566 MB of model files. After that, startup can still take time because OpenVINO and the NPU compile/load models locally.

## Distribution Policy For 0.1.0-alpha.3

0.1.0-alpha.3 may publish unsigned Windows artifacts while code signing is pending:

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
