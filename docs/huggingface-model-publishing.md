# Hugging Face Model Artifact Publishing

This document records the current publishing flow for the converted model artifacts used by NPU Dictate.

Target repository:

- `Zoomerland/local-voice-dictation-openvino`
- Visibility: public
- Repository type: model
- License: MIT

## What Gets Published

The Hugging Face model repository should contain only the selected converted artifacts and metadata:

- GigaAM v3 CTC OpenVINO NNCF INT8 bucket-400 ASR artifacts.
- Small ASR config/vocabulary files required by the local wrapper.
- RUPunct big OpenVINO FP16 static-128 punctuation artifacts.
- `MANIFEST.json` with install paths, file sizes, SHA256 checksums, source revisions, and conversion metadata.
- `README.md` model card.
- `THIRD_PARTY_NOTICES.md`.

Do not upload:

- OpenVINO cache files.
- Hugging Face local cache directories.
- Debug WAV recordings.
- Intermediate bucket/model experiments that are not the current supported profile.

## Prepare Locally

Use the project virtual environment:

```powershell
.\.venv\Scripts\python.exe tools\prepare_hf_model_repo.py
```

This creates:

```text
hf_export/local-voice-dictation-openvino/
```

The `hf_export/` directory is ignored by Git.

## Authenticate

Do not paste Hugging Face tokens into chat or commit them to the repository.

Safe local options:

```powershell
.\.venv\Scripts\hf.exe auth login
```

or for a one-shot terminal session:

```powershell
$env:HF_TOKEN = "hf_your_token_here"
```

Then verify:

```powershell
.\.venv\Scripts\hf.exe auth whoami
```

## Upload

After local authentication:

```powershell
.\.venv\Scripts\python.exe tools\prepare_hf_model_repo.py --upload --repo-id Zoomerland/local-voice-dictation-openvino
```

The upload is public by default. Add `--private` only if a private staging repository is needed.

Current public repository:

- https://huggingface.co/Zoomerland/local-voice-dictation-openvino
- Uploaded on 2026-06-18.
- Hugging Face API verification after upload: `private=false`, `license=mit`, 17 repository files.
- Remote `MANIFEST.json`: 13 artifacts, `total_size_bytes=594057141`.

## App Downloader

The in-app downloader is implemented in `tools/model_setup.py`.

It currently:

- Downloads `MANIFEST.json` first.
- Downloads each required `repo_path` for the selected app model profile.
- Verifies `size_bytes` and `sha256` after download.
- Moves files to the listed app-local `install_path` under `models/`.
- Retries failed downloads.
- Leaves partial files with a temporary `.download` suffix until verification succeeds.
- Emits status updates for manifest download, file download, verification, and retry attempts.

Still pending:

- A richer settings UI for installed models, disk usage, manual rebuild, and cache clearing.
- A determinate progress widget instead of only status-text updates plus the existing busy indicator.

## Download Verification

2026-06-18 fresh-download test:

- Downloaded remote `MANIFEST.json` from `Zoomerland/local-voice-dictation-openvino`.
- Downloaded all 13 listed artifacts into a temporary empty app root.
- Verified `size_bytes` and SHA256 for every downloaded file.
- Total downloaded artifact bytes: `594057141`.
- Elapsed time on the test connection: about `73.85` seconds.
- Result: `download_test=OK`.
