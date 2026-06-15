# Local Voice Dictation

Windows-first local dictation prototype: microphone audio goes through GigaAM v3 CTC ASR, then optional Russian punctuation restoration through RUPunct on OpenVINO/NPU, then the final text is pasted into the active field.

The repository intentionally does not store model weights, local virtual environments, recordings, or Hugging Face caches. The first launch prepares models locally.

See [ROADMAP.md](ROADMAP.md) for the current development plan.

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

## Hardware and Performance Notes

Current development machine:

- CPU: Intel Core Ultra 5 135U.
- NPU: Intel AI Boost.
- Approximate platform capability: 11 NPU TOPS, 22 total platform TOPS.

This is intentionally treated as a mainstream/weak NPU baseline. If the app is useful here, it should be practical on many newer Windows laptops.

Preliminary local measurements:

- GigaAM v3 CTC ASR has multiple local profiles.
  - `onnx-asr` INT8 CPU profile:
    - 2 seconds of audio: about 0.15 seconds after warmup.
    - 4 seconds of audio: about 0.24 seconds after warmup.
    - 8 seconds of audio: about 0.40 seconds after warmup.
  - OpenVINO NPU profiles:
    - First run for a new static bucket can spend tens of seconds compiling and caching the model.
    - The app can warm common ASR buckets at startup (`warmup_models`, `asr_warmup_buckets`) so real dictation uses already-compiled paths.
    - Current NPU buckets use a small static-shape grid (`asr_bucket_frames`).
    - Experimental chunked NPU ASR (`asr_chunked`) splits longer dictation into short static bucket runs, then stitches chunk text before punctuation.
    - Experimental VAD-segmented NPU ASR (`asr_vad_segments`) uses Silero VAD to cut audio on speech boundaries, then runs each segment through one warmed NPU bucket.
    - Fragmented NPU ASR output can trigger an experimental NPU-only retry through alternate buckets (`asr_retry_fragmented`, `asr_retry_buckets`).
    - Static feature padding is tunable (`asr_pad_mode`); the current default is `zero`, which best matched the CPU baseline on the reference voice sample.
    - The current working ASR NPU profile is `gigaam-v3-ctc-openvino-nncf-int8-b400`.
    - A short 350 ms microphone pre-roll is prepended to live recordings to avoid losing first words after hotkey/button activation.
    - On 9 live post-pre-roll debug WAV files, CPU INT8 took 10.643 seconds total and NPU took 1.831 seconds total, about 5.8x faster.
    - The same 9-file run had 8 exact CPU/NPU raw-text matches, average text diff 0.0007, and maximum diff 0.0066.
    - One 8.73-second live sample took 4.307 seconds on CPU INT8 and 0.426 seconds on NPU, about 10.1x faster.
- RUPunct punctuation restoration runs through OpenVINO and already works on NPU.
  - Warm NPU inference is around 20-30 ms for short dictation chunks.
  - Earlier OpenVINO CPU measurements were roughly 130 ms for comparable chunks.

Current NPU status:

- RUPunct: end-to-end OpenVINO/NPU inference is implemented and tested.
- GigaAM ASR: OpenVINO/NPU CTC wrappers are implemented for static-shape buckets and OpenVINO cache. The current default NPU candidate is the NNCF INT8 bucket-400 profile.
- CPU ASR uses ONNX Runtime with a dynamic time axis (`seq_len`), while the NPU path uses static OpenVINO shapes. The chunked and VAD-segmented NPU modes are practical approximations: short fixed-shape windows, optional speech-boundary splitting, then text stitching.
- GigaAM INT8 ONNX is intentionally not exposed for NPU because it compiled but produced incorrect text during local testing. This is separate from the OpenVINO NNCF INT8 profile used by the current NPU candidate.

The app must support CPU-only machines. NPU acceleration is a feature, not a hard requirement. Settings now expose separate ASR and punctuation model profiles, with CPU / GPU / NPU choices disabled until that exact model/device path is implemented and tested.

## License Notes

Do not publish converted model artifacts until each upstream license is checked again. GigaAM and `istupakov/gigaam-v3-onnx` are marked as MIT, but the RUPunct model card should be reviewed before redistributing a converted OpenVINO derivative.

For now, the project should publish code and conversion/download scripts, not bundled models.
