# Packaging Plan

This document tracks the packaging route for Local Voice Dictation after the source-based v0.1 alpha.

## Current Decision

- Build a Windows `.exe` first.
- Use a PyInstaller one-directory build, not a one-file build.
- Keep large model artifacts out of the executable and installer.
- Download model artifacts on first launch into the app-local `models/` directory.
- Prefer a user-writable install location for the first installer so app-local models, config, logs, and OpenVINO cache remain writable without elevation.

## Why One-Directory

The app depends on large native and ML packages: OpenVINO, Torch, sounddevice, NumPy, SciPy, ONNX ASR, Pillow, and Windows automation packages. A one-directory build keeps startup and troubleshooting more predictable than unpacking a one-file executable on every launch.

## Runtime Paths

Source mode:

- App root is the repository root.
- Config: `voice_dictation_config.json`.
- Models: `models/`.
- Logs: `voice_dictation.log`.

Frozen `.exe` mode:

- App root is the directory containing `LocalVoiceDictation.exe`.
- Config, models, logs, and OpenVINO cache stay next to the executable.
- The `LOCAL_VOICE_DICTATION_APP_ROOT` environment variable can override the app root for tests or portable layouts.
- The `LOCAL_VOICE_DICTATION_MUTEX_NAME` environment variable can override the single-instance mutex name for packaging smoke tests.

## Build Command

From the repository root:

```powershell
.\tools\build_windows_exe.ps1 -Clean
```

Output:

```text
dist\LocalVoiceDictation\LocalVoiceDictation.exe
```

## Smoke Checks

Fast import-only smoke check:

```powershell
.\tools\smoke_packaged_exe.ps1 -ImportOnly
```

Full model-load smoke check:

```powershell
.\tools\smoke_packaged_exe.ps1 -FullLoad
```

The full smoke check uses a temporary app root and hardlinks the existing local `models/` files into it. A fresh OpenVINO cache can make the first full packaged check slow.

Last local full packaged smoke result:

- Date: 2026-06-18.
- Result: passed.
- OpenVINO devices in packaged app: `CPU,GPU,NPU`.
- ASR profile loaded: `gigaam-v3-ctc-openvino-nncf-int8-b400` on `NPU`.
- Punctuation profile loaded: `rupunct-big-openvino-fp16-static128` on `NPU`.
- Cold temporary-cache load time: about 260 seconds.

## Installer Direction

The installer should come after the `.exe` build is stable.

Recommended first installer route:

- User-scope MSI or another per-user installer layout.
- Install into a user-writable directory, likely under `%LOCALAPPDATA%`.
- Do not install model files into `Program Files` unless model/config/cache paths are moved to `%LOCALAPPDATA%`.
- Add uninstall cleanup for app binaries, shortcuts, and optional model cache cleanup.
- Reuse the existing startup toggle, but verify it points at the installed `.exe`.

## Code Signing Direction

Before signing:

- Make the GitHub repository public.
- Publish clear license and third-party notices.
- Keep reproducible build scripts in the public repository.

Signing should cover:

- `LocalVoiceDictation.exe`.
- The installer package.

Community/open-source signing options still need a fresh release-time check before relying on them.
