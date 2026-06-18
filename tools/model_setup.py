import hashlib
import json
import shutil
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app_paths import app_root


ASR_MODEL_NAME = "gigaam-v3-ctc"
ASR_MODEL_REPO = "istupakov/gigaam-v3-onnx"
ARTIFACT_MODEL_REPO = "Zoomerland/local-voice-dictation-openvino"
ARTIFACT_MODEL_REVISION = "main"
PUNCT_MODEL_NAME = "RUPunct/RUPunct_big"
PUNCT_MAX_LEN = 128
DOWNLOAD_RETRIES = 3
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
ASR_OPENVINO_NNCF_INT8_PROFILE = "gigaam-v3-ctc-openvino-nncf-int8-b400"
PUNCT_OPENVINO_FP16_PROFILE = "rupunct-big-openvino-fp16-static128"


def repo_root():
    return app_root()


def hf_cache_dir():
    return repo_root() / ".hf"


def asr_model_dir():
    return repo_root() / "models" / "asr" / ASR_MODEL_NAME


def punct_model_dir():
    return repo_root() / "models" / "openvino" / "RUPunct_big_fp16_static128"


def artifact_manifest_cache_path():
    return repo_root() / "models" / ".manifests" / "local-voice-dictation-openvino" / "MANIFEST.json"


def emit(status_callback, message):
    if status_callback:
        status_callback(message)


def format_bytes(value):
    value = float(value or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


def format_duration(seconds):
    if seconds is None or seconds < 0:
        return "--:--"
    seconds = int(round(seconds))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_download_status(
    downloaded,
    total=None,
    *,
    started_at=None,
    now=None,
    label="models",
    item_index=None,
    item_count=None,
    overall_done=0,
    overall_total=None,
):
    now = time.monotonic() if now is None else now
    elapsed = max(0.001, now - (started_at or now))
    speed = downloaded / elapsed if downloaded > 0 else 0
    speed_text = f"{format_bytes(speed)}/s" if speed > 0 else "--"
    item_text = f"{item_index}/{item_count} " if item_index and item_count else ""

    if overall_total:
        overall_downloaded = min(int(overall_total), int(overall_done or 0) + int(downloaded or 0))
        pct = min(100, int(overall_downloaded * 100 / overall_total))
        remaining = max(0, int(overall_total) - overall_downloaded)
        eta = format_duration(remaining / speed) if speed > 0 else "--:--"
        return (
            f"Downloading models {pct}% "
            f"{format_bytes(overall_downloaded)}/{format_bytes(overall_total)}, "
            f"{format_bytes(remaining)} left, {speed_text}, ETA {eta}, {item_text}{label}"
        )

    if total:
        pct = min(100, int(downloaded * 100 / total))
        remaining = max(0, int(total) - int(downloaded or 0))
        eta = format_duration(remaining / speed) if speed > 0 else "--:--"
        return (
            f"Downloading models {pct}% "
            f"{format_bytes(downloaded)}/{format_bytes(total)}, "
            f"{format_bytes(remaining)} left, {speed_text}, ETA {eta}, {item_text}{label}"
        )

    return f"Downloading models {format_bytes(downloaded)}, {speed_text}, {item_text}{label}"


def artifact_url(repo_path, repo_id=ARTIFACT_MODEL_REPO, revision=ARTIFACT_MODEL_REVISION):
    return (
        f"https://huggingface.co/{repo_id}/resolve/{quote(revision, safe='')}/"
        f"{quote(str(repo_path).replace(chr(92), '/'), safe='/')}"
    )


def manifest_url(repo_id=ARTIFACT_MODEL_REPO, revision=ARTIFACT_MODEL_REVISION):
    return artifact_url("MANIFEST.json", repo_id, revision)


def read_json_url(url, timeout=30):
    request = Request(url, headers={"User-Agent": "NPUDictate/0.1"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def load_cached_artifact_manifest():
    path = artifact_manifest_cache_path()
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_remote_artifact_manifest(status_callback=None, force=False):
    cached = None if force else load_cached_artifact_manifest()
    if cached and cached.get("repo_id") == ARTIFACT_MODEL_REPO:
        return cached

    emit(status_callback, "Downloading model manifest")
    manifest = read_json_url(manifest_url())
    if manifest.get("repo_id") != ARTIFACT_MODEL_REPO:
        raise RuntimeError(f"Unexpected model artifact repo id: {manifest.get('repo_id')}")
    path = artifact_manifest_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return manifest


def safe_install_path(install_path, root=None):
    root = Path(root or repo_root()).resolve()
    raw = Path(str(install_path))
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError(f"Unsafe model artifact install path: {install_path}")
    target = (root / raw).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Model artifact install path escapes app root: {install_path}") from exc
    return target


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(DOWNLOAD_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_ready(artifact, root=None, verify_hash=True):
    target = safe_install_path(artifact["install_path"], root)
    if not target.exists():
        return False
    expected_size = artifact.get("size_bytes")
    if expected_size is not None and target.stat().st_size != int(expected_size):
        return False
    expected_hash = artifact.get("sha256")
    if verify_hash and expected_hash and sha256_file(target).lower() != str(expected_hash).lower():
        return False
    return True


def artifacts_for_profile(manifest, profile_id=None, component=None):
    artifacts = manifest.get("artifacts") or []
    result = []
    for artifact in artifacts:
        if profile_id is not None and artifact.get("profile_id") != profile_id:
            continue
        if component is not None and artifact.get("component") != component:
            continue
        result.append(artifact)
    return result


def profile_artifacts_ready(manifest, profile_id, component=None, root=None, verify_hash=True):
    artifacts = artifacts_for_profile(manifest, profile_id, component)
    return bool(artifacts) and all(
        artifact_ready(artifact, root, verify_hash=verify_hash) for artifact in artifacts
    )


def download_url_to_file(
    url,
    target,
    expected_size=None,
    status_callback=None,
    label="models",
    item_index=None,
    item_count=None,
    overall_done=0,
    overall_total=None,
):
    target = Path(target)
    tmp = target.with_name(target.name + ".download")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    if tmp.exists():
        tmp.unlink()

    request = Request(url, headers={"User-Agent": "NPUDictate/0.1"})
    try:
        with urlopen(request, timeout=60) as response, tmp.open("wb") as file:
            total = expected_size or response.headers.get("Content-Length")
            total = int(total) if total else None
            downloaded = 0
            started_at = time.monotonic()
            last_emit = 0.0
            while True:
                chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                file.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if status_callback and (now - last_emit >= 0.5 or (total and downloaded >= total)):
                    last_emit = now
                    emit(
                        status_callback,
                        format_download_status(
                            downloaded,
                            total,
                            started_at=started_at,
                            now=now,
                            label=label,
                            item_index=item_index,
                            item_count=item_count,
                            overall_done=overall_done,
                            overall_total=overall_total,
                        ),
                    )
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    if expected_size is not None and tmp.stat().st_size != int(expected_size):
        actual_size = tmp.stat().st_size
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"Downloaded size mismatch for {label}: {actual_size} != {expected_size}"
        )
    return tmp


def install_artifact(
    artifact,
    status_callback=None,
    root=None,
    item_index=None,
    item_count=None,
    overall_done=0,
    overall_total=None,
):
    target = safe_install_path(artifact["install_path"], root)
    if artifact_ready(artifact, root):
        return target

    url = artifact_url(artifact["repo_path"])
    label = Path(artifact["repo_path"]).name
    last_error = None
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            emit(status_callback, f"Downloading models {label}")
            tmp = download_url_to_file(
                url,
                target,
                expected_size=artifact.get("size_bytes"),
                status_callback=status_callback,
                label=label,
                item_index=item_index,
                item_count=item_count,
                overall_done=overall_done,
                overall_total=overall_total,
            )
            emit(status_callback, f"Verifying models {label}")
            actual_hash = sha256_file(tmp)
            expected_hash = str(artifact.get("sha256") or "").lower()
            if expected_hash and actual_hash.lower() != expected_hash:
                tmp.unlink(missing_ok=True)
                raise RuntimeError(
                    f"SHA256 mismatch for {label}: {actual_hash.lower()} != {expected_hash}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.unlink(missing_ok=True)
            shutil.move(str(tmp), str(target))
            return target
        except (HTTPError, URLError, TimeoutError, RuntimeError, OSError) as exc:
            last_error = exc
            if attempt >= DOWNLOAD_RETRIES:
                break
            emit(status_callback, f"Retrying models {label} ({attempt + 1}/{DOWNLOAD_RETRIES})")
            time.sleep(min(1.0 * attempt, 3.0))
    raise RuntimeError(f"Failed to download model artifact {label}: {last_error}")


def ensure_profile_artifacts(profile_id, component=None, status_callback=None):
    manifest = load_remote_artifact_manifest(status_callback)
    artifacts = artifacts_for_profile(manifest, profile_id, component)
    if not artifacts:
        raise RuntimeError(f"No model artifacts found for profile: {profile_id}")

    missing = [artifact for artifact in artifacts if not artifact_ready(artifact, verify_hash=True)]
    total_size = sum(int(artifact.get("size_bytes") or 0) for artifact in missing) or None
    if missing:
        emit(
            status_callback,
            f"Preparing model download {len(missing)} files"
            + (f", {format_bytes(total_size)}" if total_size else ""),
        )

    downloaded_size = 0
    for index, artifact in enumerate(missing, 1):
        install_artifact(
            artifact,
            status_callback=status_callback,
            item_index=index,
            item_count=len(missing),
            overall_done=downloaded_size,
            overall_total=total_size,
        )
        downloaded_size += int(artifact.get("size_bytes") or 0)
    return manifest


def asr_model_ready():
    model_dir = asr_model_dir()
    required = ("config.json", "v3_ctc.int8.onnx", "v3_vocab.txt")
    return all((model_dir / name).exists() for name in required)


def asr_openvino_model_ready():
    model_dir = asr_model_dir()
    required = ("config.json", "v3_ctc.onnx", "v3_vocab.txt")
    return all((model_dir / name).exists() for name in required)


def asr_openvino_artifact_model_ready():
    manifest = load_cached_artifact_manifest()
    if manifest and profile_artifacts_ready(
        manifest,
        ASR_OPENVINO_NNCF_INT8_PROFILE,
        "asr",
        verify_hash=False,
    ):
        return True
    model_dir = repo_root() / "models" / "asr" / "gigaam-v3-ctc-openvino-int8-calib96"
    required = ("v3_ctc_bucket400_nncf_int8.xml", "v3_ctc_bucket400_nncf_int8.bin")
    return all((model_dir / name).exists() for name in required) and all(
        (asr_model_dir() / name).exists() for name in ("config.json", "v3_vocab.txt")
    )


def punct_model_ready():
    model_dir = punct_model_dir()
    required = ("config.json", "openvino_model.xml", "openvino_model.bin", "tokenizer.json")
    return all((model_dir / name).exists() for name in required)


def ensure_asr_model(status_callback=None):
    if asr_model_ready():
        return asr_model_dir()

    emit(status_callback, "Downloading ASR")
    model_dir = asr_model_dir()
    model_dir.mkdir(parents=True, exist_ok=True)
    filenames = ("config.json", "v3_vocab.txt", "v3_ctc.int8.onnx")
    total_size = None
    downloaded_size = 0
    for index, filename in enumerate(filenames, 1):
        target = model_dir / filename
        if target.exists():
            downloaded_size += target.stat().st_size
            continue
        tmp = download_url_to_file(
            artifact_url(filename, repo_id=ASR_MODEL_REPO),
            target,
            status_callback=status_callback,
            label=filename,
            item_index=index,
            item_count=len(filenames),
            overall_done=downloaded_size,
            overall_total=total_size,
        )
        target.unlink(missing_ok=True)
        shutil.move(str(tmp), str(target))
        downloaded_size += target.stat().st_size

    if not asr_model_ready():
        import onnx_asr

        onnx_asr.load_model(ASR_MODEL_NAME, model_dir, quantization="int8")
    return asr_model_dir()


def ensure_asr_openvino_model(status_callback=None, profile_id=None):
    if profile_id == ASR_OPENVINO_NNCF_INT8_PROFILE:
        if asr_openvino_artifact_model_ready():
            return asr_model_dir()
        ensure_profile_artifacts(ASR_OPENVINO_NNCF_INT8_PROFILE, "asr", status_callback)
        return asr_model_dir()

    if asr_openvino_model_ready():
        return asr_model_dir()

    emit(status_callback, "Downloading ASR NPU")
    model_dir = asr_model_dir()
    model_dir.mkdir(parents=True, exist_ok=True)
    filenames = ("config.json", "v3_vocab.txt", "v3_ctc.onnx")
    downloaded_size = 0
    for index, filename in enumerate(filenames, 1):
        target = model_dir / filename
        if target.exists():
            downloaded_size += target.stat().st_size
            continue
        tmp = download_url_to_file(
            artifact_url(filename, repo_id=ASR_MODEL_REPO),
            target,
            status_callback=status_callback,
            label=filename,
            item_index=index,
            item_count=len(filenames),
            overall_done=downloaded_size,
        )
        target.unlink(missing_ok=True)
        shutil.move(str(tmp), str(target))
    return model_dir


def ensure_punct_model(status_callback=None, max_len=PUNCT_MAX_LEN):
    if punct_model_ready():
        return punct_model_dir()

    try:
        emit(status_callback, "Downloading punct")
        ensure_profile_artifacts(PUNCT_OPENVINO_FP16_PROFILE, "punctuation", status_callback)
        if punct_model_ready():
            return punct_model_dir()
    except Exception as exc:
        emit(status_callback, f"Downloading punct failed: {type(exc).__name__}")

    emit(status_callback, "Downloading punct")
    import openvino as ov
    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    model_dir = punct_model_dir()
    model_dir.mkdir(parents=True, exist_ok=True)
    hf_cache_dir().mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(
        PUNCT_MODEL_NAME,
        cache_dir=str(hf_cache_dir()),
        strip_accents=False,
        add_prefix_space=True,
    )
    model = AutoModelForTokenClassification.from_pretrained(
        PUNCT_MODEL_NAME,
        cache_dir=str(hf_cache_dir()),
    )
    model.eval()

    tokenizer.save_pretrained(model_dir)
    model.config.save_pretrained(model_dir)

    emit(status_callback, "Converting punct")
    encoded = tokenizer(
        "это короткий тест для подготовки модели",
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=max_len,
    )
    inputs = {
        key: value
        for key, value in encoded.items()
        if key in {"input_ids", "attention_mask", "token_type_ids"}
    }

    with torch.no_grad():
        ov_model = ov.convert_model(model, example_input=inputs)

    ov_model.reshape({key: [1, max_len] for key in inputs})
    ov.save_model(ov_model, model_dir / "openvino_model.xml", compress_to_fp16=True)
    return model_dir


def main():
    ensure_asr_model(print)
    ensure_punct_model(print)
    print("Models are ready.")


if __name__ == "__main__":
    main()
