import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_REPO_ID = "Zoomerland/local-voice-dictation-openvino"
DEFAULT_OUTPUT_DIR = Path("hf_export") / "local-voice-dictation-openvino"

ASR_SOURCE_REVISION = "322c3b29492673eb7d0b434bfa9dfb8653e34d02"
GIGAAM_BASE_REVISION = "ec1dc1f01d0d627ab2c0d3acc1e235702300d95e"
RUPUNCT_SOURCE_REVISION = "d05f73afd84b57a45b83238c35b866bc625fe247"

ARTIFACTS = [
    {
        "component": "asr",
        "profile_id": "gigaam-v3-ctc-openvino-nncf-int8-b400",
        "description": "GigaAM v3 CTC OpenVINO NNCF INT8 bucket-400 XML",
        "source_path": "models/asr/gigaam-v3-ctc-openvino-int8-calib96/v3_ctc_bucket400_nncf_int8.xml",
        "repo_path": "asr/gigaam-v3-ctc-openvino-int8-calib96/v3_ctc_bucket400_nncf_int8.xml",
        "install_path": "models/asr/gigaam-v3-ctc-openvino-int8-calib96/v3_ctc_bucket400_nncf_int8.xml",
        "source_repo": "istupakov/gigaam-v3-onnx",
        "source_revision": ASR_SOURCE_REVISION,
        "conversion": "OpenVINO NNCF INT8, bucket=400, calibration set calib96",
    },
    {
        "component": "asr",
        "profile_id": "gigaam-v3-ctc-openvino-nncf-int8-b400",
        "description": "GigaAM v3 CTC OpenVINO NNCF INT8 bucket-400 weights",
        "source_path": "models/asr/gigaam-v3-ctc-openvino-int8-calib96/v3_ctc_bucket400_nncf_int8.bin",
        "repo_path": "asr/gigaam-v3-ctc-openvino-int8-calib96/v3_ctc_bucket400_nncf_int8.bin",
        "install_path": "models/asr/gigaam-v3-ctc-openvino-int8-calib96/v3_ctc_bucket400_nncf_int8.bin",
        "source_repo": "istupakov/gigaam-v3-onnx",
        "source_revision": ASR_SOURCE_REVISION,
        "conversion": "OpenVINO NNCF INT8, bucket=400, calibration set calib96",
    },
    {
        "component": "asr",
        "profile_id": "gigaam-v3-ctc-openvino-nncf-int8-b400",
        "description": "GigaAM v3 config required by the local wrapper",
        "source_path": "models/asr/gigaam-v3-ctc/config.json",
        "repo_path": "asr/gigaam-v3-ctc/config.json",
        "install_path": "models/asr/gigaam-v3-ctc/config.json",
        "source_repo": "istupakov/gigaam-v3-onnx",
        "source_revision": ASR_SOURCE_REVISION,
    },
    {
        "component": "asr",
        "profile_id": "gigaam-v3-ctc-openvino-nncf-int8-b400",
        "description": "GigaAM v3 CTC vocabulary required by the local wrapper",
        "source_path": "models/asr/gigaam-v3-ctc/v3_vocab.txt",
        "repo_path": "asr/gigaam-v3-ctc/v3_vocab.txt",
        "install_path": "models/asr/gigaam-v3-ctc/v3_vocab.txt",
        "source_repo": "istupakov/gigaam-v3-onnx",
        "source_revision": ASR_SOURCE_REVISION,
    },
    {
        "component": "punctuation",
        "profile_id": "rupunct-big-openvino-fp16-static128",
        "description": "RUPunct config",
        "source_path": "models/openvino/RUPunct_big_fp16_static128/config.json",
        "repo_path": "punctuation/RUPunct_big_fp16_static128/config.json",
        "install_path": "models/openvino/RUPunct_big_fp16_static128/config.json",
        "source_repo": "RUPunct/RUPunct_big",
        "source_revision": RUPUNCT_SOURCE_REVISION,
        "conversion": "OpenVINO FP16 static max_len=128",
    },
    {
        "component": "punctuation",
        "profile_id": "rupunct-big-openvino-fp16-static128",
        "description": "RUPunct OpenVINO model XML",
        "source_path": "models/openvino/RUPunct_big_fp16_static128/openvino_model.xml",
        "repo_path": "punctuation/RUPunct_big_fp16_static128/openvino_model.xml",
        "install_path": "models/openvino/RUPunct_big_fp16_static128/openvino_model.xml",
        "source_repo": "RUPunct/RUPunct_big",
        "source_revision": RUPUNCT_SOURCE_REVISION,
        "conversion": "OpenVINO FP16 static max_len=128",
    },
    {
        "component": "punctuation",
        "profile_id": "rupunct-big-openvino-fp16-static128",
        "description": "RUPunct OpenVINO model weights",
        "source_path": "models/openvino/RUPunct_big_fp16_static128/openvino_model.bin",
        "repo_path": "punctuation/RUPunct_big_fp16_static128/openvino_model.bin",
        "install_path": "models/openvino/RUPunct_big_fp16_static128/openvino_model.bin",
        "source_repo": "RUPunct/RUPunct_big",
        "source_revision": RUPUNCT_SOURCE_REVISION,
        "conversion": "OpenVINO FP16 static max_len=128",
    },
    {
        "component": "punctuation",
        "profile_id": "rupunct-big-openvino-fp16-static128",
        "description": "RUPunct tokenizer",
        "source_path": "models/openvino/RUPunct_big_fp16_static128/tokenizer.json",
        "repo_path": "punctuation/RUPunct_big_fp16_static128/tokenizer.json",
        "install_path": "models/openvino/RUPunct_big_fp16_static128/tokenizer.json",
        "source_repo": "RUPunct/RUPunct_big",
        "source_revision": RUPUNCT_SOURCE_REVISION,
    },
    {
        "component": "punctuation",
        "profile_id": "rupunct-big-openvino-fp16-static128",
        "description": "RUPunct tokenizer config",
        "source_path": "models/openvino/RUPunct_big_fp16_static128/tokenizer_config.json",
        "repo_path": "punctuation/RUPunct_big_fp16_static128/tokenizer_config.json",
        "install_path": "models/openvino/RUPunct_big_fp16_static128/tokenizer_config.json",
        "source_repo": "RUPunct/RUPunct_big",
        "source_revision": RUPUNCT_SOURCE_REVISION,
    },
    {
        "component": "punctuation",
        "profile_id": "rupunct-big-openvino-fp16-static128",
        "description": "OpenVINO tokenizer XML",
        "source_path": "models/openvino/RUPunct_big_fp16_static128/openvino_tokenizer.xml",
        "repo_path": "punctuation/RUPunct_big_fp16_static128/openvino_tokenizer.xml",
        "install_path": "models/openvino/RUPunct_big_fp16_static128/openvino_tokenizer.xml",
        "source_repo": "RUPunct/RUPunct_big",
        "source_revision": RUPUNCT_SOURCE_REVISION,
        "conversion": "OpenVINO tokenizer artifact",
    },
    {
        "component": "punctuation",
        "profile_id": "rupunct-big-openvino-fp16-static128",
        "description": "OpenVINO tokenizer weights",
        "source_path": "models/openvino/RUPunct_big_fp16_static128/openvino_tokenizer.bin",
        "repo_path": "punctuation/RUPunct_big_fp16_static128/openvino_tokenizer.bin",
        "install_path": "models/openvino/RUPunct_big_fp16_static128/openvino_tokenizer.bin",
        "source_repo": "RUPunct/RUPunct_big",
        "source_revision": RUPUNCT_SOURCE_REVISION,
        "conversion": "OpenVINO tokenizer artifact",
    },
    {
        "component": "punctuation",
        "profile_id": "rupunct-big-openvino-fp16-static128",
        "description": "OpenVINO detokenizer XML",
        "source_path": "models/openvino/RUPunct_big_fp16_static128/openvino_detokenizer.xml",
        "repo_path": "punctuation/RUPunct_big_fp16_static128/openvino_detokenizer.xml",
        "install_path": "models/openvino/RUPunct_big_fp16_static128/openvino_detokenizer.xml",
        "source_repo": "RUPunct/RUPunct_big",
        "source_revision": RUPUNCT_SOURCE_REVISION,
        "conversion": "OpenVINO detokenizer artifact",
    },
    {
        "component": "punctuation",
        "profile_id": "rupunct-big-openvino-fp16-static128",
        "description": "OpenVINO detokenizer weights",
        "source_path": "models/openvino/RUPunct_big_fp16_static128/openvino_detokenizer.bin",
        "repo_path": "punctuation/RUPunct_big_fp16_static128/openvino_detokenizer.bin",
        "install_path": "models/openvino/RUPunct_big_fp16_static128/openvino_detokenizer.bin",
        "source_repo": "RUPunct/RUPunct_big",
        "source_revision": RUPUNCT_SOURCE_REVISION,
        "conversion": "OpenVINO detokenizer artifact",
    },
]


def repo_root():
    return Path(__file__).resolve().parents[1]


def git_revision(root):
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_artifact(root, output_dir, item):
    src = root / item["source_path"]
    if not src.exists():
        raise FileNotFoundError(f"Missing required artifact: {src}")
    dst = output_dir / item["repo_path"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    size = dst.stat().st_size
    result = dict(item)
    result["size_bytes"] = size
    result["sha256"] = sha256_file(dst)
    return result


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def format_size(size):
    return f"{size / (1024 * 1024):.2f} MB"


def manifest_for(root, output_dir, repo_id, artifacts):
    total_size = sum(item["size_bytes"] for item in artifacts)
    return {
        "schema_version": 1,
        "repo_id": repo_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "created_by_app_revision": git_revision(root),
        "license": "mit",
        "release_channel": "v0.1-alpha",
        "description": "Converted OpenVINO artifacts for NPU Dictate.",
        "total_size_bytes": total_size,
        "source_revisions": {
            "ai-sage/GigaAM-v3": GIGAAM_BASE_REVISION,
            "istupakov/gigaam-v3-onnx": ASR_SOURCE_REVISION,
            "RUPunct/RUPunct_big": RUPUNCT_SOURCE_REVISION,
        },
        "artifacts": artifacts,
    }


def readme_text(manifest):
    rows = []
    for item in manifest["artifacts"]:
        rows.append(
            "| {component} | `{profile}` | `{path}` | {size} | `{sha}` |".format(
                component=item["component"],
                profile=item["profile_id"],
                path=item["repo_path"],
                size=format_size(item["size_bytes"]),
                sha=item["sha256"][:16] + "...",
            )
        )
    rows_text = "\n".join(rows)
    return f"""---
license: mit
language:
- ru
tags:
- openvino
- npu
- automatic-speech-recognition
- punctuation
- russian
- local-voice-dictation
library_name: openvino
---

# NPU Dictate OpenVINO Artifacts

This repository contains converted model artifacts used by NPU Dictate.

The main application repository downloads these files after installation. Large
model files are intentionally not bundled inside the application executable or
installer.

## Contents

| Component | Profile | File | Size | SHA256 |
| --- | --- | --- | --- | --- |
{rows_text}

See `MANIFEST.json` for the full file list, install paths, SHA256 checksums,
source revisions, and conversion metadata.

## Source Models

- GigaAM-v3 base model: `ai-sage/GigaAM-v3`
- GigaAM-v3 ONNX export: `istupakov/gigaam-v3-onnx`
- RUPunct big: `RUPunct/RUPunct_big`

These artifacts are derivative conversions prepared for NPU Dictate.
They are not a new model family.

## License

The upstream sources used for these artifacts are observed as MIT-licensed.
See `THIRD_PARTY_NOTICES.md` for attribution and notice details.

## Integrity

Consumers should verify every downloaded file against `MANIFEST.json` before
using it. The NPU Dictate downloader is expected to use `repo_path`,
`install_path`, `size_bytes`, and `sha256` from that manifest.
"""


def notices_text():
    mit_text = """Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""
    return f"""# Third-Party Notices

These converted artifacts are prepared for NPU Dictate from upstream
MIT-licensed model/runtime projects.

## GigaAM / GigaAM-v3

- Upstream: https://github.com/salute-developers/GigaAM
- Base model: https://huggingface.co/ai-sage/GigaAM-v3
- Observed license: MIT
- Notice observed in upstream LICENSE:

MIT License

Copyright (c) 2024 GigaChat Team

{mit_text}

## GigaAM-v3 ONNX

- Upstream: https://huggingface.co/istupakov/gigaam-v3-onnx
- Observed license: MIT
- Notice observed in upstream LICENSE.txt:

MIT License

Copyright (c) 2024 GigaChat Team

{mit_text}

## onnx-asr

- Upstream: https://github.com/istupakov/onnx-asr
- Observed license: MIT
- Notice observed in upstream LICENSE:

MIT License

Copyright (c) 2025 Ilya Stupakov

{mit_text}

## RUPunct big

- Upstream: https://huggingface.co/RUPunct/RUPunct_big
- Observed license: MIT via Hugging Face model card metadata.
- No separate LICENSE file was present in the upstream model repository at the
  time this package metadata was prepared.

## Silero VAD

- Upstream: https://github.com/snakers4/silero-vad
- Used by the application through `onnx-asr` for VAD-segmented ASR.
- Observed license: MIT
- Notice observed in upstream LICENSE:

MIT License

Copyright (c) 2020-present Silero Team

{mit_text}
"""


def gitattributes_text():
    return """*.bin filter=lfs diff=lfs merge=lfs -text
*.onnx filter=lfs diff=lfs merge=lfs -text
*.xml text eol=lf
*.json text eol=lf
*.md text eol=lf
*.txt text eol=lf
"""


def prepare(args):
    root = repo_root()
    output_dir = (root / args.output_dir).resolve()
    if args.clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    artifacts = [copy_artifact(root, output_dir, item) for item in ARTIFACTS]
    manifest = manifest_for(root, output_dir, args.repo_id, artifacts)

    write_text(output_dir / "README.md", readme_text(manifest))
    write_text(output_dir / "THIRD_PARTY_NOTICES.md", notices_text())
    write_text(output_dir / ".gitattributes", gitattributes_text())
    write_text(
        output_dir / "MANIFEST.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    return output_dir, manifest


def upload_folder(args, output_dir):
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise SystemExit(
            "huggingface_hub is not installed. Use the project .venv or install requirements.txt."
        ) from exc

    api = HfApi()
    api.create_repo(
        repo_id=args.repo_id,
        repo_type="model",
        private=args.private,
        exist_ok=True,
    )
    api.upload_folder(
        folder_path=str(output_dir),
        repo_id=args.repo_id,
        repo_type="model",
        commit_message=args.commit_message,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Prepare and optionally upload the NPU Dictate Hugging Face model artifact repository."
    )
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-clean", dest="clean", action="store_false")
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--private", action="store_true")
    parser.add_argument(
        "--commit-message",
        default="Upload NPU Dictate OpenVINO artifacts",
    )
    args = parser.parse_args()
    args.clean = bool(args.clean)

    output_dir, manifest = prepare(args)
    print(f"prepared={output_dir}")
    print(f"repo_id={args.repo_id}")
    print(f"files={len(manifest['artifacts'])}")
    print(f"size_mb={manifest['total_size_bytes'] / (1024 * 1024):.2f}")

    if args.upload:
        upload_folder(args, output_dir)
        print(f"uploaded=https://huggingface.co/{args.repo_id}")
    else:
        print("upload=skipped")


if __name__ == "__main__":
    main()
