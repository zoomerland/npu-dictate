# NPU Dictate

NPU Dictate is a Windows-first, local-first dictation utility. It records microphone audio, recognizes speech with GigaAM v3 CTC, optionally restores Russian punctuation/capitalization with RUPunct, and inserts the final text into the active text field.

The project is still an alpha/prototype. Unsigned packaged `.exe` and MSI pre-release builds are available for testing, while source mode remains the main development path.

See [ROADMAP.md](ROADMAP.md) for the current development plan.

App code is licensed under the [MIT License](LICENSE). Model weights and converted model artifacts are governed by their upstream licenses and are not bundled in this repository.

See the [Code signing policy](docs/code-signing-policy.md) for the planned Windows signing process and current SignPath Foundation application status.

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

See [docs/tested-hardware.md](docs/tested-hardware.md) for the current tested hardware matrix.

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

## Developer Packaged Build

Build a PyInstaller one-directory `.exe`:

```powershell
.\tools\build_windows_exe.ps1 -Clean
```

Output:

```text
dist\NPUDictate\NPUDictate.exe
```

Run a fast packaged import smoke check:

```powershell
.\tools\smoke_packaged_exe.ps1 -ImportOnly
```

Run a full packaged model-load smoke check:

```powershell
.\tools\smoke_packaged_exe.ps1 -FullLoad
```

See [docs/packaging-plan.md](docs/packaging-plan.md) for the current packaging plan and known installer/signing decisions.

Build a developer MSI from the packaged `.exe` directory:

```powershell
dotnet tool restore
.\tools\build_windows_msi.ps1 -SkipExeBuild
```

The default MSI path is `dist\installer\NPUDictate-0.1.0-alpha.1.msi`. The installer is not signed yet and does not bundle model artifacts.

Smoke-check the MSI without installing it:

```powershell
.\tools\smoke_windows_msi.ps1
```

## Local Smoke Checks

Run the lightweight developer smoke checks after changing model profiles, paste behavior, insertion spacing, or diagnostics:

```powershell
.\.venv\Scripts\python.exe .\tools\smoke_checks.py
```

The smoke checks validate config normalization, CPU fallback profile selection, OpenVINO hardware probing, insertion spacing rules, clipboard paste/restore behavior through mocks, model directories, and the local RUPunct CPU path when model files are already present.

## Diagnostics

Print a readable environment report:

```powershell
.\.venv\Scripts\python.exe .\tools\doctor.py
```

Print the same report as JSON:

```powershell
.\.venv\Scripts\python.exe .\tools\doctor.py --json
```

The doctor report includes Python and package versions, config summary, model paths, OpenVINO devices, selected CPU/GPU/NPU devices, audio input devices, and recent log lines. It does not download models or start the UI.

## Models and First Launch

Model artifacts are intentionally not stored in Git. First launch prepares local model files under `models/`.

Current upstream sources:

- ASR: `gigaam-v3-ctc`, currently backed by `istupakov/gigaam-v3-onnx` through `onnx-asr` and direct Hugging Face downloads.
- Punctuation: `RUPunct/RUPunct_big`, downloaded from Hugging Face and converted locally to a static OpenVINO FP16 model.
- Converted OpenVINO artifacts for the current tested NPU profiles: `Zoomerland/local-voice-dictation-openvino`.

The current NPU OpenVINO artifacts are downloaded from Hugging Face into the app-local `models/` directory. The downloader reads `MANIFEST.json`, downloads required files with retries, verifies file size and SHA256, then installs them into their final `models/...` paths.

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
- UI localization exists for English and Russian, but UI language is separate from ASR language. English UI does not imply English speech recognition support.
- User-provided custom models are out of scope for v0.1.
- The current v0.1 manual paste matrix passed for browser fields, Notepad, Windows Search, Telegram Desktop, ChatGPT/Codex-style inputs, and standard Windows text fields.
- Untested rich editors may still behave differently from plain text inputs.
- Clipboard paste is used intentionally for reliability; direct text injection is deferred.
- Punctuation quality depends on ASR quality and available text context before the cursor.
- Long dictation passed the v0.1 manual acceptance pass, but fast speech, heavy system/NPU load, and exact repeated-word counts still need more tuning.
- First model preparation and first OpenVINO/NPU compile can be slow.
- The current packaged artifacts are unsigned pre-release builds.

## Install And Uninstall

The MSI installs NPU Dictate per-user under `%LOCALAPPDATA%\NPUDictate` and creates a Start Menu shortcut.

Uninstall through Windows Settings:

1. Open Settings.
2. Go to Apps > Installed apps.
3. Find `NPU Dictate`.
4. Choose Uninstall.

The MSI removes installed application binaries and shortcuts. Downloaded model files may remain in the app-local directory until a dedicated cache cleanup option is added.

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
- Converted OpenVINO artifacts are downloaded from `Zoomerland/local-voice-dictation-openvino`; incomplete files use a temporary `.download` suffix and are replaced only after checksum verification.
- Keep virtual environment dependencies aligned with `requirements.txt`.

### NPU is not available

- Copy diagnostics and check `hardware.devices`.
- Expected Intel NPU machines should report a device such as `NPU`.
- If `NPU` is missing, update/install the Intel NPU driver and re-test with `start_voice_dictation_debug.cmd`.
- Switch ASR to the CPU ONNX profile and punctuation to CPU while investigating NPU/OpenVINO driver issues.

## License Notes

The application code is MIT licensed.

The current source-only v0.1 model-license audit was completed on 2026-06-18. Current ASR, punctuation, VAD, and model-loading upstreams are observed as MIT-licensed, and model weights / converted artifacts are not bundled in this repository.

Do not publish converted model artifacts until each upstream license is checked again and the published artifact includes upstream attribution, MIT notices, exact source metadata where practical, conversion metadata, and a clear derivative-conversion note.

See [docs/model-sources-and-licenses.md](docs/model-sources-and-licenses.md) for the current model source and license matrix.

For now, publish code plus download/conversion scripts, not bundled model weights.

The current `0.1.0-alpha.1` release notes draft is in [docs/release-notes-v0.1-draft.md](docs/release-notes-v0.1-draft.md).
