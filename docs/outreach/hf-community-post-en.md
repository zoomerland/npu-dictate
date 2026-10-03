# NPU Dictate alpha.5: testing the converted OpenVINO artifacts

These artifacts are used by [NPU Dictate](https://github.com/zoomerland/npu-dictate), a local Windows dictation app. The [alpha.5 prerelease](https://github.com/zoomerland/npu-dictate/releases/tag/v0.1.0-alpha.5) includes unsigned EXE/MSI builds; model files are downloaded separately. The converted OpenVINO artifacts in this repository are checked against the manifest's file sizes and SHA256 hashes.

The tested NPU setup is Intel Core Ultra 5 135U / Intel AI Boost, Windows 11, OpenVINO 2026.2.0. The current NPU speech profile is GigaAM v3 CTC, OpenVINO NNCF INT8, static feature bucket 400. Punctuation uses RUPunct_big FP16 with a static 128-token input. Speech recognition in the app is Russian only. English UI localization is not English ASR support. NVIDIA and GPU profiles are not validated.

The app has a separate CPU ASR profile. Audio capture, VAD and other surrounding work still use the CPU even when inference is on the NPU. The first compilation/cache preparation can be slow; warm starts are a separate case. Initial model download requires internet, but normal dictation afterwards is local.

Alpha.5 improves long-text punctuation handling with overlapping token-budgeted windows and adds UX safeguards. It does not replace the ASR artifacts with a new model. Converted weights retain their upstream licenses; the app's MIT license does not replace those licenses.

Feedback from other Intel NPU machines would help. For artifact/download problems, include the affected filename, error and hardware/runtime versions here. For app UI, pasting or recognition problems, please use the [app issue tracker](https://github.com/zoomerland/npu-dictate/issues), so reports stay in one place. Please redact diagnostics and use non-sensitive example phrases rather than private audio, transcripts or full log files.
