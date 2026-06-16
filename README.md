# Local Voice Dictation

Local Voice Dictation is a Windows-first, local-first dictation utility. It records microphone audio, recognizes speech with GigaAM v3 CTC, optionally restores Russian punctuation/capitalization with RUPunct, and inserts the final text into the active text field.

The project is still an alpha/prototype. There is no packaged `.exe` or installer yet; run it from source.

See [ROADMAP.md](ROADMAP.md) for the current development plan.

## What Works Today

- Floating always-on-top dictation overlay.
- Hold-to-talk and toggle recording modes.
- Global dictation hotkey and overlay show/hide hotkey.
- Tray menu for settings, hide/show, diagnostics, and quit.
- Local ASR with GigaAM v3 CTC.
- Local Russian punctuation restoration with RUPunct through OpenVINO.
- NPU-accelerated ASR and punctuation profiles on the current Intel NPU test laptop.
- CPU ASR and punctuation fallback profiles for machines without a working NPU path.
- Context-aware insertion spacing and punctuation context before the cursor.
- Clipboard-based paste with optional clipboard restoration after successful paste.

## Supported Environment

Current target:

- Windows 11.
- Python 3.12.
- Built-in or external microphone supported by `sounddevice`.
- Optional Intel NPU for accelerated profiles.

Reference development laptop:

- Intel Core Ultra 5 135U.
- Intel AI Boost NPU.
- About 11 NPU TOPS / 22 total platform TOPS.

This is intentionally treated as a weak/mainstream NPU baseline, not a high-end accelerator.

## Quick Start

Create a virtual environment and install dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start the app:

```powershell
.\start_voice_dictation.cmd
```

Start with a visible console for logs and errors:

```powershell
.\start_voice_dictation_debug.cmd
```

Default controls:

- `F8`: dictation hotkey.
- `Ctrl+Alt+Shift+D`: show or hide the overlay.
- Default mode is `hold`: hold `F8`, speak, release.
- In settings, switch to `toggle` to press once to start and once to stop.

## Models and First Launch

Model artifacts are intentionally not stored in Git. First launch prepares local model files under `models/`.

Current upstream sources:

- ASR: `gigaam-v3-ctc`, currently backed by `istupakov/gigaam-v3-onnx` through `onnx-asr` and direct Hugging Face downloads.
- Punctuation: `RUPunct/RUPunct_big`, downloaded from Hugging Face and converted locally to a static OpenVINO FP16 model.

Generated local artifacts:

- `models/asr/gigaam-v3-ctc/`
- `models/openvino/RUPunct_big_fp16_static128/`
- `models/openvino/cache/`

The first NPU/OpenVINO run can spend noticeable time compiling and caching models. Later starts should be faster once the OpenVINO cache is warm.

## Privacy and Offline Behavior

The intended runtime flow is local:

- Microphone audio is processed on the local machine.
- ASR and punctuation run locally.
- Text insertion uses local Windows focus, UI Automation, clipboard, and keyboard events.

Network access is needed for first-time model download/preparation unless the models are already present locally. After that, normal dictation should not require internet access.

Local files that may contain private data:

- `voice_dictation_config.json`
- `voice_dictation.log`
- `recordings/debug_dictation/` when debug audio saving is enabled

These files are ignored by Git.

## CPU vs NPU

The app has separate model profiles. A device selector shows CPU / GPU / NPU choices, and unsupported choices are disabled for the selected model profile.

Current pipeline:

| Stage | Current status |
| --- | --- |
| Audio capture | CPU/Windows audio stack through `sounddevice`. |
| VAD segmentation | CPU through Silero/Torch when enabled. |
| ASR CPU profile | `GigaAM v3 CTC (ONNX INT8)`, CPU only. |
| ASR NPU profile | `GigaAM v3 CTC (OpenVINO NNCF INT8 b400)`, tested on Intel NPU with VAD segmentation and fuzzy stitching. |
| Punctuation | `RUPunct big (OpenVINO FP16 static 128)`, available on CPU and NPU. |
| Postprocessing | CPU string cleanup, casing, context-aware insertion spacing, and paste handling. |

CPU-only machines can use the CPU ASR profile and the CPU punctuation device. NPU remains the preferred path for the current alpha on supported Intel NPU laptops because it is much faster on the reference machine.

On startup, the app runs a soft OpenVINO hardware probe in the background loading thread. It logs the OpenVINO version, reported devices, device names, selected OpenVINO devices, and warnings when a selected device such as `NPU` is not reported by OpenVINO. The same data is included in copied diagnostics.

## Preliminary Benchmarks

These numbers are local development measurements, not a formal benchmark suite.

| Task | Device/profile | Result | Notes |
| --- | --- | --- | --- |
| GigaAM ASR, 9 live post-pre-roll WAV files | CPU INT8 | 10.643 s total | Warm CPU baseline. |
| GigaAM ASR, same 9 files | NPU OpenVINO NNCF INT8 b400 | 1.831 s total | About 5.8x faster than CPU total. |
| GigaAM ASR text parity, same 9 files | CPU vs NPU | 8/9 exact matches | Average diff 0.0007, maximum diff 0.0066. |
| GigaAM ASR, one 8.73 s live sample | CPU INT8 | 4.307 s | Warm CPU run. |
| GigaAM ASR, same 8.73 s sample | NPU OpenVINO NNCF INT8 b400 | 0.426 s | About 10.1x faster. |
| RUPunct short chunks | NPU OpenVINO FP16 static 128 | about 20-30 ms | Warm inference. |
| RUPunct comparable chunks | OpenVINO CPU, earlier measurements | about 130 ms | Older local comparison. |
| RUPunct direct smoke test | OpenVINO CPU | about 0.3-0.5 s | Short strings, end-to-end local load path verified. |

Saved-sample ASR tuning report:

- 46 saved dictation WAV files.
- 36 exact CPU/NPU raw-text matches.
- Average CPU/NPU text diff: 0.0021.
- Maximum diff: 0.0185.
- No samples above 0.02 diff.

## Known Limitations

- Russian dictation is the current focus.
- UI localization exists for English and Russian, but speech model language profiles are not a general user feature yet.
- Paste reliability still needs testing across more applications.
- Some rich editors may behave differently from plain text inputs.
- Clipboard paste is used intentionally for reliability; direct text injection is deferred.
- Punctuation quality depends on ASR quality and available text context before the cursor.
- Long dictation, fast speech, and heavy system/NPU load still need more tuning.
- First model preparation and first OpenVINO/NPU compile can be slow.
- There is no installer, code signing, or packaged app yet.

## Troubleshooting

### The app stays on loading

- Start with `start_voice_dictation_debug.cmd` and inspect the console.
- Check `voice_dictation.log`.
- First launch or first NPU compile can be much slower than later starts.
- If it repeatedly stalls on NPU model loading, switch the ASR model/device to the CPU ONNX profile in settings or edit `voice_dictation_config.json`.

### Nothing is inserted

- Check whether the dictated text was copied to the clipboard.
- If paste fails, the app should leave the dictated text in the clipboard so manual `Ctrl+V` still works.
- Try Notepad first to separate paste/focus issues from a specific application.
- Use the diagnostics action from the tray/settings menu and inspect recent focus/paste log lines.
- Diagnostics also include OpenVINO hardware info, selected devices, and recent log tail.

### The wrong field receives text

- Click the intended input once and try again.
- Test with the overlay hidden if the target app is sensitive to focus changes.
- Some Chromium/Electron and rich text editors can expose focus differently through UI Automation.

### The first word is missing

- The app keeps a warm microphone stream and prepends a short pre-roll buffer.
- If first words are still lost, increase `audio_pre_roll_ms` in `voice_dictation_config.json`.
- Avoid starting speech before the hotkey/button press is registered.

### Recognition quality is worse than expected

- Try a shorter phrase first.
- Check that Windows microphone effects/noise suppression are not fighting the model.
- Compare ASR CPU/NPU output with `compare_asr` enabled if debugging quality.
- Heavy CPU/NPU load can affect live capture and processing timing.

### Models fail to download or convert

- Make sure internet access is available for first model preparation.
- Delete only the incomplete model subfolder under `models/` and start again.
- Keep virtual environment dependencies aligned with `requirements.txt`.

### NPU is not available

- Copy diagnostics and check `hardware.devices`.
- Expected Intel NPU machines should report a device such as `NPU`.
- If `NPU` is missing, update/install the Intel NPU driver and re-test with `start_voice_dictation_debug.cmd`.
- Switch ASR to the CPU ONNX profile and punctuation to CPU while investigating NPU/OpenVINO driver issues.

## License Notes

Do not publish converted model artifacts until each upstream license is checked again. GigaAM and `istupakov/gigaam-v3-onnx` have been treated as MIT during local testing, but all upstream model cards should be reviewed before redistributing converted derivatives.

For now, publish code plus download/conversion scripts, not bundled model weights.
