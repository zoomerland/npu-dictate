# v0.1 Alpha Release Notes Draft

Status: draft. Do not publish as a GitHub Release until the remaining manual UX checks are complete.

## Summary

Local Voice Dictation v0.1 alpha is a source-based Windows prototype for local Russian dictation. It records microphone audio, runs local ASR, restores punctuation/capitalization, and inserts the result into the active text field.

This alpha is meant for technical users who are comfortable running a Python project from source.

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

## Distribution Policy For v0.1

v0.1 should be source-only or script-based:

- Publish source code.
- Publish setup instructions.
- Publish model download/conversion code.
- Do not ship a packaged `.exe` yet.
- Do not ship an installer yet.
- Do not bundle model weights or converted OpenVINO artifacts.

Packaging, installer work, icon/branding, uninstall behavior, and code signing remain later milestones.

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

See `docs/model-sources-and-licenses.md`.

## Known Limitations

- Russian speech recognition is the current focus.
- UI language is independent from speech recognition language. English/Russian UI does not imply English ASR support.
- User-provided custom models are out of scope for v0.1.
- Paste/focus behavior still needs a broader application matrix.
- Long dictation and fast speech still need more manual testing.
- GPU profiles are not considered tested yet.
- First model preparation and first OpenVINO/NPU compilation can be slow.
- No packaged app, installer, or code signing yet.

## Suggested Pre-Release Checklist

- Run `tools/smoke_checks.py`.
- Run `tools/doctor.py`.
- Verify paste into Codex Desktop input.
- Verify paste into Chrome search and web textareas.
- Verify paste into Notepad.
- Verify at least one long dictation sample with pauses and cancellation.
- Re-check upstream model licenses before publishing any converted artifacts.
