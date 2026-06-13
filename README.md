# Local Voice Dictation

Windows-first local dictation prototype: microphone audio goes through GigaAM v3 CTC ASR, then optional Russian punctuation restoration through RUPunct on OpenVINO/NPU, then the final text is pasted into the active field.

The repository intentionally does not store model weights, local virtual environments, recordings, or Hugging Face caches. The first launch prepares models locally.

## Current Flow

1. Hold or toggle the dictation hotkey.
2. Record audio from the selected Windows input device.
3. Transcribe locally with `gigaam-v3-ctc` through `onnx-asr`.
4. Restore Russian punctuation/capitalization with a locally converted `RUPunct/RUPunct_big` OpenVINO model.
5. Copy or paste the result into the active field.

## Setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start the app:

```powershell
.\start_voice_dictation.cmd
```

For visible logs and errors:

```powershell
.\start_voice_dictation_debug.cmd
```

## Hotkeys

- `F8`: default dictation hotkey.
- `Ctrl+Alt+Shift+D`: show or hide the floating button.

The default mode is `hold`: hold `F8`, speak, release. In settings, switch to `toggle` to press once to start and once to stop.

## Models

The app prepares these local artifacts on first launch:

- ASR: `gigaam-v3-ctc` from the `onnx-asr` model mapping, currently backed by `istupakov/gigaam-v3-onnx`.
- Punctuation: `RUPunct/RUPunct_big`, downloaded from Hugging Face and converted locally to a static OpenVINO model for short dictation chunks.

Generated artifacts live under `models/` and are ignored by Git.

## License Notes

Do not publish converted model artifacts until each upstream license is checked again. GigaAM and `istupakov/gigaam-v3-onnx` are marked as MIT, but the RUPunct model card should be reviewed before redistributing a converted OpenVINO derivative.

For now, the project should publish code and conversion/download scripts, not bundled models.
