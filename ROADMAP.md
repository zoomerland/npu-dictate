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
- [x] First-run model preparation for ASR and punctuation.
- [x] Debug log for paste/focus behavior.
- [ ] Test paste reliability in:
  - Codex Desktop input.
  - Chrome search field.
  - Chrome web textareas.
  - Notepad.
  - Telegram/Slack/Discord-like apps.
  - Office/Word-like editors.
- [ ] Add a user-visible fallback when paste fails.
- [ ] Add a small diagnostics view or "copy debug info" action.
- [ ] Long dictation test: pauses, silence, repeated phrases, and cancellation.
- [ ] Decide how to handle leading/trailing spaces around inserted text.
- [ ] Add context-aware insertion:
  - Read a small text fragment before the cursor when possible.
  - Use previous sentence or current unfinished sentence as punctuation context.
  - Send context plus new dictation to the postprocessor.
  - Insert only the newly dictated segment back into the field.

## Milestone 1: Overlay and Settings UX

Goal: make the app feel like a real desktop utility instead of a prototype.

- [ ] Make the entire overlay draggable, including the main button.
- [x] Persist overlay visibility in config.
- [ ] Persist overlay position after drag and restore it on next launch.
- [ ] Add overlay size presets:
  - Small.
  - Medium.
  - Large.
- [ ] Add overlay shape presets:
  - Square.
  - Rounded square.
  - Circle.
- [ ] Add compact/full overlay modes:
  - Button only.
  - Button plus status.
  - Button plus status and hotkey hint.
- [ ] Improve recording/loading/transcribing visual states.
- [ ] Add settings warning when closing with unsaved changes.
- [ ] Add Apply / Save / Cancel behavior.
- [ ] Add real hotkey capture controls:
  - "Assign" button.
  - Capture one key or a key combination.
  - Support dictation hotkey.
  - Support overlay show/hide hotkey.
  - Validate conflicts and empty hotkeys.
- [ ] Add tray icon:
  - Restore overlay on click.
  - Hide overlay.
  - Open settings.
  - Quit.
  - Show current status.
- [ ] Add optional startup behavior:
  - Create/remove Startup folder shortcut for script mode.
  - Revisit after installer packaging.

## Milestone 2: Interface Localization

Goal: make the app interface available in multiple languages.

This milestone is about UI language, not ASR language.

- [ ] Add UI language selector to settings.
- [ ] Store UI language in config.
- [ ] Add translation dictionary or resource files.
- [ ] Localize overlay text:
  - Recording.
  - Transcribing.
  - Loading.
  - Ready.
  - Copied/Pasted.
- [ ] Localize settings window.
- [ ] Localize tray menu.
- [ ] Localize errors and model setup messages.
- [ ] Initial UI languages:
  - English.
  - Russian.
- [ ] Optional later UI languages:
  - Spanish.
  - German.
  - French.
- [ ] Keep ASR model language separate from UI language.

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
- [ ] Document exact upstream sources and licenses.
- [ ] Decide whether to publish a Hugging Face model repository for converted artifacts.
- [ ] If publishing converted artifacts, include license metadata and attribution.
- [ ] Keep user-provided custom models out of v0.1 unless core flow is stable.

## Milestone 4: NPU Work

Goal: move more of the useful pipeline to NPU without sacrificing reliability.

- [x] RUPunct OpenVINO static model runs on NPU.
- [x] GigaAM ONNX can compile on NPU with static input shapes.
- [ ] Build an OpenVINO/NPU GigaAM encoder wrapper.
- [ ] Keep existing CTC decoder behavior.
- [ ] Benchmark CPU vs NPU:
  - Cold load.
  - Warm inference.
  - Short phrases.
  - Long dictation.
  - CPU usage.
  - Battery/resource impact.
- [ ] Add device selector per model: Auto / CPU / GPU / NPU.
- [ ] Add startup hardware capability checks.
- [ ] Document tested Intel NPU devices.

## Milestone 5: Public v0.1 Release

Goal: publish a usable alpha for technical users.

- [ ] Improve README:
  - What the app does.
  - Supported OS.
  - Hardware expectations.
  - Model download behavior.
  - Privacy/offline behavior.
  - Known limitations.
- [ ] Add screenshots or short demo GIF/video.
- [ ] Add CPU vs NPU section.
- [ ] Add troubleshooting:
  - Microphone permissions.
  - Paste/focus problems.
  - Model download problems.
  - NPU driver/OpenVINO issues.
- [ ] Add license for the app code.
- [ ] Create GitHub release notes.
- [ ] Keep release source-only or script-based until packaging is ready.

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
