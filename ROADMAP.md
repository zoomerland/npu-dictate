# Roadmap

This project is a Windows-first, local-first dictation app. The core promise is simple: fast offline speech-to-text, practical insertion into any active text field, and NPU acceleration where it actually helps.

The app is not ready for packaging yet. The near-term goal is to stabilize the daily-use workflow before building an installer or signing anything.

## Product Principles

- Local-first and free by default.
- Do not bundle large model weights in the Git repository.
- Download or convert models on first launch from official upstream sources.
- Treat NPU support as a product feature, with CPU fallback where needed.
- Keep packaging, installer work, and code signing until the app UX is stable.
- Prefer predictable Windows behavior over clever UI tricks.

## Milestone 0: Dictation Loop Stabilization

Goal: make the current Russian dictation loop reliable enough for daily use.

- [x] Local ASR with GigaAM v3 CTC.
- [x] Local punctuation with RUPunct on OpenVINO/NPU.
- [x] Floating overlay button.
- [x] Hold-to-talk and toggle recording modes.
- [x] Paste through clipboard and Windows input events.
- [x] Add clipboard restore setting:
  - Temporarily use clipboard for reliable paste.
  - Restore previous text clipboard after successful paste.
  - Keep dictated text in clipboard when paste fails so the user can paste manually.
- [x] First-run model preparation for ASR and punctuation.
- [x] Debug log for paste/focus behavior.
- [ ] Test paste reliability in:
  - Added `docs/manual-paste-test-plan.md`.
  - Added local browser test page: `tools/paste_test_page.html`.
  - Browser test page B1-B8 passed in Chrome; results recorded in `docs/manual-paste-test-results.md`.
  - Notepad N1-N3 passed; Windows Search N4 passed after stale-clipboard mitigation and clipboard-restore regression.
  - Codex Desktop input.
  - Chrome search field.
  - Chrome web textareas.
  - Notepad.
  - Telegram/Slack/Discord-like apps.
  - Office/Word-like editors.
- [x] Add a user-visible fallback when paste fails.
- [x] Add a small diagnostics view or "copy debug info" action.
- [x] Add local smoke checks:
  - Validate config normalization and model/device profile selection.
  - Validate OpenVINO hardware probing.
  - Validate insertion spacing and clipboard paste/restore behavior without touching real user input.
  - Smoke-test local RUPunct CPU fallback when model files are present.
- [x] Add local doctor diagnostics:
  - Report Python and dependency versions.
  - Report config, model paths, OpenVINO devices, audio input devices, and recent logs.
  - Support human-readable output and JSON output.
- [ ] Long dictation test: pauses, silence, repeated phrases, and cancellation.
- [x] Decide how to handle leading/trailing spaces around inserted text:
  - Add a leading space when the cursor follows normal text and the inserted fragment starts with a word.
  - Avoid adding a leading space before inserted punctuation such as commas or periods.
  - Avoid duplicating a space when the context already ends with whitespace.
  - Keep trailing-space behavior controlled by the existing setting, but apply it through the same insertion-boundary cleanup.
- [x] Fix startup state transitions:
  - Avoid briefly showing an idle/ready-looking state before model loading begins.
  - Show model-loading/busy state immediately after app start.
  - Keep the overlay disabled or clearly busy until models are ready.
- [ ] Add context-aware insertion:
  - [x] Read a small text fragment before the cursor when possible.
  - [x] Use previous sentence or current unfinished sentence as punctuation context.
  - [x] Send context plus new dictation to the postprocessor.
  - [x] Insert only the newly dictated segment back into the field.
  - [ ] Test and tune in Chromium/Electron and native Win32 inputs.
  - [ ] Optional full-field repunctuation mode:
    - Re-read the full text field after insertion.
    - Run punctuation/casing over the full field text.
    - Replace the field only through a safe editor-specific path.
    - Do not use selection-based fallbacks that can destroy user text.

## Milestone 1: Overlay and Settings UX

Goal: make the app feel like a real desktop utility instead of a prototype.

- [x] Make the entire overlay draggable, including the main button.
- [x] Persist overlay visibility in config.
- [x] Persist overlay position after drag and restore it on next launch.
- [x] Add overlay size presets:
  - Small.
  - Medium.
  - Large.
- [x] Add overlay shape presets:
  - Square.
  - Rounded square.
  - Circle.
  - Implemented with Canvas drawing and Tk transparent color instead of the previous WinAPI window-region prototype.
- [x] Add overlay opacity slider in settings:
  - Store opacity in config.
  - Apply opacity to the overlay window immediately.
  - Keep a safe minimum opacity so the overlay cannot become invisible.
- [x] Add compact/full overlay modes:
  - Button only.
  - Button plus status.
  - Button plus status and hotkey hint.
- [ ] Round UI corners where the Windows/Tk stack allows it:
  - [x] Overlay window shape.
  - [x] Overlay button and frame internals.
  - [x] Settings controls or grouped sections.
  - [ ] Context menu/tray menu where practical.
- [x] Increase context menu size to match the settings readability scale.
- [x] Improve recording/loading/transcribing visual states.
- [x] Add settings warning when closing with unsaved changes.
- [x] Add Apply / Save / Cancel behavior.
- [x] Add real hotkey capture controls:
  - "Assign" button.
  - Capture one key or a key combination.
  - Support dictation hotkey.
  - Support overlay show/hide hotkey.
  - Validate conflicts and empty hotkeys.
- [x] Add tray icon:
  - Restore overlay on click.
  - Hide overlay.
  - Open settings.
  - Quit.
  - Show current status.
- [x] Add optional startup behavior:
  - Create/remove Startup folder shortcut for script mode.
  - Revisit after installer packaging.

## Milestone 2: Interface Localization

Goal: make the app interface available in multiple languages.

This milestone is about UI language, not ASR language.

- [x] Add UI language selector to settings.
- [x] Store UI language in config.
- [x] Add translation dictionary or resource files.
- [x] Localize overlay text:
  - Recording.
  - Transcribing.
  - Loading.
  - Ready.
  - Copied/Pasted.
- [x] Localize settings window.
- [x] Localize settings option values.
- [x] Localize tray menu.
- [x] Localize errors and model setup messages.
- [x] Initial UI languages:
  - [x] English.
  - [x] Russian.
- [ ] Optional later UI languages:
  - Spanish.
  - German.
  - French.
- [x] Keep ASR model language separate from UI language:
  - README documents that English/Russian UI does not imply English/Russian ASR model support.
  - Custom ASR language profiles remain deferred until custom model support exists.

## Milestone 3: Model Management and Licensing

Goal: make model setup transparent and legally clean.

- [x] Keep model artifacts out of Git.
- [x] Download/prepare models on first run.
- [ ] Add visible progress for model downloads and conversion.
- [ ] Replace indeterminate progress with per-model progress where possible.
- [ ] Add retry and failure messages for model setup.
- [ ] Add "Models" settings section:
  - Installed models.
  - Disk usage.
  - Download/rebuild action.
  - Clear cache action.
- [ ] Review upstream licenses before redistributing any converted model.
- [x] Document exact upstream sources and licenses:
  - Added `docs/model-sources-and-licenses.md`.
  - Recorded current GigaAM, ONNX ASR, and RUPunct upstream links and observed license labels.
  - Kept redistribution review as a release gate.
- [ ] Decide whether to publish a Hugging Face model repository for converted artifacts.
- [ ] If publishing converted artifacts, include license metadata and attribution.
- [x] Keep user-provided custom models out of v0.1 unless core flow is stable:
  - v0.1 release notes draft lists custom user models as out of scope.

## Milestone 4: NPU Work

Goal: move more of the useful pipeline to NPU without sacrificing reliability.

- [x] RUPunct OpenVINO static model runs on NPU.
- [x] GigaAM ONNX can compile on NPU with static input shapes.
- [x] Build an OpenVINO/NPU GigaAM CTC wrapper.
- [x] Keep existing CTC decoder behavior.
- [x] Run end-to-end GigaAM ASR inference through NPU.
- [x] Disable the GigaAM INT8/NPU path after it compiled but produced incorrect text.
- [x] Add experimental chunked NPU ASR:
  - Use one short static bucket for longer dictation.
  - Split audio into overlapping chunks.
  - Log per-chunk timing, frames, bucket, and raw text.
  - Stitch raw chunk text before punctuation.
- [x] Add experimental VAD-segmented NPU ASR:
  - Use Silero VAD to split audio on speech boundaries.
  - Run speech segments through one warmed NPU bucket.
  - Keep VAD loading lazy so app startup is not blocked by the segmenter.
- [x] Bring saved-sample NPU ASR output close to the CPU baseline:
  - Use the OpenVINO NNCF INT8 bucket-400 ASR profile on NPU.
  - Use VAD segmentation, overlap-aware stitching, fuzzy duplicate trimming, and final ASR artifact cleanup.
  - Reference report: 46 saved dictation WAV files, 36 exact CPU/NPU text matches.
  - Average CPU/NPU text diff: 0.0021; maximum diff: 0.0185; no samples above 0.02.
  - Treat the remaining mismatches as minor recognition variants unless live testing shows a real regression.
- [x] Stabilize live recording startup:
  - Start audio capture before UI Automation context lookup.
  - Keep a warm microphone stream and prepend a short 350 ms pre-roll buffer.
  - Clear the pre-roll buffer after each recording to avoid carrying speech into the next dictation.
  - Live quick-start tests preserved the first words without repeating prior-recording tails.
- [ ] Tune chunked NPU ASR quality:
  - Compare bucket 400 vs 1000.
  - Compare VAD bucket 800 vs fixed chunk buckets.
  - Tune overlap and silence-biased cut points.
  - Test fast speech and long dictation from saved WAV files.
  - Compare against the CPU dynamic-shape baseline.
- [ ] Benchmark CPU vs NPU:
  - [x] Preliminary warm ASR benchmark on 9 live post-pre-roll debug WAV files:
    - CPU INT8 total: 10.643 seconds.
    - NPU OpenVINO NNCF INT8 bucket-400 total: 1.831 seconds.
    - Total speedup: about 5.8x.
    - Exact CPU/NPU raw-text matches: 8/9.
    - Average text diff: 0.0007; maximum diff: 0.0066.
  - Cold load.
  - Warm inference.
  - Short phrases.
  - Long dictation.
  - CPU usage.
  - Battery/resource impact.
- [x] Publish benchmark notes for the current test laptop:
  - Intel Core Ultra 5 135U.
  - Intel AI Boost NPU.
  - About 11 NPU TOPS / 22 total platform TOPS.
  - Treat this as a weak/mainstream NPU baseline, not a high-end accelerator.
- [x] Document what currently runs on NPU and what still runs on CPU.
- [x] Provide CPU fallback for systems without NPU:
  - ASR can use the ONNX INT8 CPU profile.
  - RUPunct OpenVINO FP16 can use the CPU device.
- [x] Make CPU-only mode obvious in settings and documentation:
  - CPU is available in ASR and punctuation device selectors for tested profiles.
  - README documents the CPU-only path and NPU troubleshooting fallback.
- [x] Add ASR and punctuation model selectors for the currently supported local profiles.
- [x] Show CPU / GPU / NPU availability per selected model and disable unsupported devices.
- [ ] Add real fallback profiles after each model/device combination is tested:
  - [x] RUPunct OpenVINO FP16 CPU fallback.
  - [ ] GPU profiles.
  - [ ] Additional ASR OpenVINO fallback profiles beyond the current tested CPU/NPU paths.
- [x] Add startup hardware capability checks:
  - Probe OpenVINO version and available devices in the background loading thread.
  - Log device names, selected OpenVINO devices, and missing-device warnings.
  - Include hardware probe results in copied diagnostics.
- [x] Document tested Intel NPU devices:
  - Added `docs/tested-hardware.md`.
  - Documented the current Intel Core Ultra 5 135U / Intel AI Boost baseline.

## Milestone 5: Public v0.1 Release

Goal: publish a usable alpha for technical users.

- [x] Improve README:
  - [x] What the app does.
  - [x] Supported OS.
  - [x] Hardware expectations.
  - [x] Model download behavior.
  - [x] Privacy/offline behavior.
  - [x] Known limitations.
- [ ] Add screenshots or short demo GIF/video.
- [x] Add CPU vs NPU section.
- [x] Include preliminary benchmark table:
  - [x] RUPunct CPU vs NPU latency.
  - [x] GigaAM CPU ASR latency.
  - [x] GigaAM NPU benchmark.
- [x] Explain CPU-only support for users without NPU.
- [x] Add troubleshooting:
  - [x] Microphone permissions.
  - [x] Paste/focus problems.
  - [x] Model download problems.
  - [x] NPU driver/OpenVINO issues.
- [x] Add license for the app code:
  - Added MIT `LICENSE` for application code.
  - Kept model weights and converted artifacts under upstream model licenses.
- [x] Create GitHub release notes:
  - Added `docs/release-notes-v0.1-draft.md` as the v0.1 alpha release notes draft.
- [x] Keep release source-only or script-based until packaging is ready:
  - v0.1 release notes draft explicitly excludes packaged `.exe`, installer, bundled model weights, and code signing.

## Milestone 6: Packaging and Installer

Goal: ship a normal Windows app after the UX is stable.

Do this last.

- [ ] Choose final app name.
- [ ] Choose app icon and visual identity.
- [ ] Package to `.exe`.
- [ ] Create installer.
- [ ] Decide installer technology.
- [ ] Decide model download location and cache location for installed builds.
- [ ] Add uninstall behavior.
- [ ] Add startup toggle for installed builds.
- [ ] Research code signing:
  - Certificate options.
  - Cost.
  - Individual vs organization signing.
  - SmartScreen reputation implications.
- [ ] Sign installer and app binaries if practical.

## Test Matrix

Keep this list short and practical while the app is young.

- Windows 11.
- Intel Core Ultra laptop with Intel NPU.
- Built-in microphone array.
- Hold-to-talk with overlay button.
- Hold-to-talk with hotkey.
- Toggle mode with overlay button.
- Toggle mode with hotkey.
- Paste into Chromium/Electron text fields.
- Paste into native Win32 text fields.
- Paste after switching tabs and windows.
- Long dictation.
- Silence and accidental short recordings.

## Deferred Ideas

These are valuable, but not v0.1 blockers.

- Custom user models.
- ASR language profiles beyond Russian after custom model support exists.
- Auto language detection for speech recognition.
- Cloud fallback.
- Voice commands.
- Per-application profiles.
- Direct text injection without clipboard.
- Rich text editor integration.
- Full plugin system.
