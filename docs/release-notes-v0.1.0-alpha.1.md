# NPU Dictate 0.1.0-alpha.1 Release Notes

Status: unsigned public pre-release candidate for SignPath Foundation application prep.

## Summary

NPU Dictate 0.1.0-alpha.1 is a Windows prototype for local Russian dictation. It records microphone audio, runs local ASR, restores punctuation/capitalization, and inserts the result into the active text field.

This alpha is meant for technical users who are comfortable with unsigned Windows pre-release software or running a Python project from source.

## Highlights

- Local-first dictation flow with no cloud service required after first model preparation.
- GigaAM v3 CTC ASR.
- RUPunct punctuation/capitalization restoration.
- NPU-accelerated ASR and punctuation on the reference Intel Core Ultra laptop.
- CPU fallback for ASR and punctuation.
- Floating overlay, tray menu, hold-to-talk and toggle modes.
- Configurable dictation and overlay hotkeys.
- UI localization for English and Russian.
- Context-aware insertion spacing and punctuation context before the cursor.
- Clipboard-based paste with optional restoration of the previous text clipboard after successful paste.
- Local smoke checks and environment doctor diagnostics.

## Distribution Policy For 0.1.0-alpha.1

0.1.0-alpha.1 may publish unsigned Windows artifacts while code signing is pending:

- Publish source code.
- Publish setup instructions.
- Publish model download/conversion code.
- Download current converted OpenVINO artifacts from `Zoomerland/local-voice-dictation-openvino` at first setup.
- Publish the unsigned packaged app archive and MSI for technical testing.
- Clearly label packaged artifacts as unsigned pre-release builds.
- Do not bundle model weights or converted OpenVINO artifacts.

Code signing remains pending through the SignPath Foundation application.

## Tested Reference Hardware

- Windows 11.
- Intel Core Ultra 5 135U.
- Intel AI Boost NPU.
- OpenVINO 2026.2.0.
- Built-in microphone array.

See `docs/tested-hardware.md`.

## Current Model Sources

- GigaAM-v3 ONNX: `istupakov/gigaam-v3-onnx`.
- RUPunct big: `RUPunct/RUPunct_big`.
- Silero VAD: loaded through `onnx-asr` for VAD-segmented NPU ASR.
- Converted OpenVINO artifacts: `Zoomerland/local-voice-dictation-openvino`.

Model-license audit completed on 2026-06-18. Current ASR, punctuation, VAD, and model-loading upstreams are observed as MIT-licensed. See `docs/model-sources-and-licenses.md`.

## Known Limitations

- Russian speech recognition is the current focus.
- UI language is independent from speech recognition language. English/Russian UI does not imply English ASR support.
- User-provided custom models are out of scope for v0.1.
- Manual paste/focus checks passed for the current v0.1 application matrix.
- Long dictation passed the v0.1 manual acceptance pass; fast speech and exact repeated-word counts still need more tuning.
- GPU profiles are not considered tested yet.
- First model preparation and first OpenVINO/NPU compilation can be slow.
- First converted-artifact download requires internet access and about 566 MB of model files.
- Packaged app and MSI artifacts are unsigned until the SignPath Foundation flow is approved and configured.

## Suggested Pre-Release Checklist

- Run `tools/smoke_checks.py`.
- Run `tools/doctor.py`.
- Paste matrix: completed for Codex/ChatGPT-style inputs, Chrome/browser fields, Telegram Desktop, Notepad, Windows Search, and standard Windows text fields.
- Long dictation matrix: completed for immediate start, long paragraphs, pauses, silence, repeated words, fast speech, accidental silence, too-short recording, and overlay drag cancellation.
- Do not publish converted model artifacts without bundled upstream attribution, MIT notices, exact source metadata where practical, conversion metadata, and a derivative-conversion note.
