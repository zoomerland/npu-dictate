import hashlib
import json
import os
import re
import stat
import threading
import time
from functools import lru_cache, wraps
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app_paths import user_data_root


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
_DOWNLOAD_LOCKS = {}
_DOWNLOAD_LOCKS_GUARD = threading.Lock()


def repo_root():
    return user_data_root()


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
    transferred=None,
):
    now = time.monotonic() if now is None else now
    elapsed = max(0.001, now - (started_at if started_at is not None else now))
    transferred = downloaded if transferred is None else transferred
    speed = transferred / elapsed if transferred > 0 else 0
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
    try:
        with path.open("r", encoding="utf-8") as file:
            manifest = json.load(file)
        return manifest if isinstance(manifest, dict) else None
    except (OSError, UnicodeError, ValueError):
        return None


def load_remote_artifact_manifest(status_callback=None, force=False):
    cached = None if force else load_cached_artifact_manifest()
    if valid_artifact_manifest(cached):
        return cached

    emit(status_callback, "Downloading model manifest")
    manifest = read_json_url(manifest_url())
    if not valid_artifact_manifest(manifest):
        raise RuntimeError("Invalid model artifact manifest")
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


@lru_cache(maxsize=64)
def cached_sha256(path, size, mtime_ns, ctime_ns):
    # Metadata is part of the key so unchanged startup checks do not reread weights.
    return sha256_file(path)


def model_file_ready(path):
    path = Path(path)
    try:
        if not path.is_file() or path.stat().st_size <= 0:
            return False
        if path.suffix == ".json":
            with path.open("r", encoding="utf-8-sig") as file:
                return isinstance(json.load(file), dict)
        return True
    except (OSError, UnicodeError, ValueError):
        return False


def artifact_ready(artifact, root=None, verify_hash=True):
    try:
        target = safe_install_path(artifact["install_path"], root)
        if not model_file_ready(target):
            return False
        stat = target.stat()
        expected_size = artifact.get("size_bytes")
        if expected_size is not None and stat.st_size != int(expected_size):
            return False
        expected_hash = artifact.get("sha256")
        if verify_hash and expected_hash:
            fingerprint = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            digest = cached_sha256(str(target), *fingerprint)
            after = target.stat()
            if fingerprint != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                return False
            if digest.lower() != str(expected_hash).lower():
                return False
    except (OSError, TypeError, ValueError, KeyError, AttributeError):
        return False
    return True


def valid_artifact_manifest(manifest):
    if not isinstance(manifest, dict) or manifest.get("repo_id") != ARTIFACT_MODEL_REPO:
        return False
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return False
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            return False
        for key in ("install_path", "repo_path", "profile_id", "component"):
            if not isinstance(artifact.get(key), str) or not artifact[key].strip():
                return False
        repo_path = artifact["repo_path"].replace("\\", "/")
        remote_path = PurePosixPath(repo_path)
        if (not remote_path.parts or remote_path.is_absolute() or ".." in remote_path.parts
                or ":" in remote_path.parts[0] or "\x00" in repo_path
                or repo_path != repo_path.strip() or repo_path != remote_path.as_posix()):
            return False
        try:
            safe_install_path(artifact["install_path"])
        except (OSError, ValueError):
            return False
        size = artifact.get("size_bytes")
        if size is not None and (type(size) is not int or size <= 0):
            return False
        digest = artifact.get("sha256")
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)):
            return False
    return True


def artifacts_for_profile(manifest, profile_id=None, component=None):
    if not valid_artifact_manifest(manifest):
        return []
    artifacts = manifest["artifacts"]
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


class _DownloadProtocolError(RuntimeError):
    pass


def _download_lock(target):
    _check_download_path(target)
    key = os.path.normcase(str(Path(target).resolve()))
    with _DOWNLOAD_LOCKS_GUARD:
        return _DOWNLOAD_LOCKS.setdefault(key, threading.RLock())


def _serialize_download(function):
    @wraps(function)
    def serialized(url, target, *args, **kwargs):
        with _download_lock(target):
            return function(url, target, *args, **kwargs)
    return serialized


def _check_download_path(path):
    # Reject links/junctions before reads, writes, replacement or narrow cleanup.
    path = Path(path).absolute()
    for entry in (path, *path.parents):
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise OSError("Unsafe download link/reparse path")
        if entry == path:
            if not stat.S_ISREG(info.st_mode):
                raise OSError("Download path is not a regular file")
        elif not stat.S_ISDIR(info.st_mode):
            raise OSError("Download parent is not a directory")


def _download_paths(target):
    partial = Path(target).with_name(Path(target).name + ".download")
    return partial, partial.with_name(partial.name + ".json")


def _clear_download_state(target):
    partial, metadata = _download_paths(target)
    paths = (partial, metadata, metadata.with_name(metadata.name + ".tmp"))
    for path in paths:
        _check_download_path(path)
    for path in paths:
        path.unlink(missing_ok=True)


def _strong_etag(value):
    return (isinstance(value, str) and len(value) <= 1024
            and re.fullmatch(r'"[\x21\x23-\x7e\x80-\xff]*"', value) is not None)


def _save_download_state(target, state):
    partial, metadata = _download_paths(target)
    temporary = metadata.with_name(metadata.name + ".tmp")
    for path in (partial, metadata, temporary):
        _check_download_path(path)
    size = partial.stat().st_size
    if not 0 < size < state["total"]:
        _clear_download_state(target)
        return
    state = dict(state, bytes=size, prefix_sha256=sha256_file(partial))
    with temporary.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(state, file, sort_keys=True)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, metadata)


def _load_download_state(target, identity):
    partial, metadata = _download_paths(target)
    for path in (partial, metadata, metadata.with_name(metadata.name + ".tmp")):
        _check_download_path(path)
    try:
        if metadata.stat().st_size > 8192:
            return None
        with metadata.open("r", encoding="utf-8") as file:
            state = json.load(file)
        if (not isinstance(state, dict)
                or any(k not in state or type(state[k]) is not type(v) or state[k] != v
                       for k, v in identity.items())
                or not _strong_etag(state.get("etag"))
                or type(state.get("total")) is not int
                or type(state.get("bytes")) is not int
                or not 0 < state["bytes"] < state["total"]
                or (identity["expected_size"] is not None
                    and state["total"] != identity["expected_size"])
                or partial.stat().st_size != state["bytes"]
                or sha256_file(partial) != state.get("prefix_sha256")):
            return None
        return state
    except (FileNotFoundError, UnicodeError, ValueError):
        return None


def _header_length(headers):
    value = headers.get("Content-Length")
    if value is None:
        return None
    if not re.fullmatch(r"[0-9]+", value):
        raise _DownloadProtocolError("Invalid download Content-Length")
    return int(value)


def _install_download(tmp, target):
    _, metadata = _download_paths(target)
    temporary = metadata.with_name(metadata.name + ".tmp")
    for path in (tmp, target, metadata, temporary):
        _check_download_path(path)
    metadata.unlink(missing_ok=True)
    temporary.unlink(missing_ok=True)
    os.replace(tmp, target)


@_serialize_download
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
    expected_sha256=None,
):
    target = Path(target)
    _check_download_path(target)
    tmp, metadata = _download_paths(target)
    expected_size = int(expected_size) if expected_size is not None else None
    if expected_size is not None and expected_size < 0:
        raise ValueError(f"Invalid expected size for {label}: {expected_size}")
    identity = {"version": 1, "source_sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
                "expected_size": expected_size,
                "expected_sha256": str(expected_sha256).lower() if expected_sha256 else None}
    state = _load_download_state(target, identity)
    tmp.parent.mkdir(parents=True, exist_ok=True)
    if state is None:
        _clear_download_state(target)
    offset = state["bytes"] if state else 0
    headers = {"User-Agent": "NPUDictate/0.1", "Accept-Encoding": "identity"}
    if state:
        headers.update({"Range": f"bytes={offset}-", "If-Range": state["etag"]})
    request = Request(url, headers=headers)
    resumable = None
    try:
        try:
            response = urlopen(request, timeout=60)
        except HTTPError as exc:
            if exc.code != 416 or not state:
                raise
            exc.close()
            # Exactly one full-request fallback; a 416 never proves local completeness.
            _clear_download_state(target)
            state, offset = None, 0
            response = urlopen(Request(url, headers={"User-Agent": "NPUDictate/0.1",
                                                   "Accept-Encoding": "identity"}), timeout=60)
        with response:
            status = getattr(response, "status", 200)
            encoding = response.headers.get("Content-Encoding", "identity").lower()
            if encoding != "identity":
                raise _DownloadProtocolError("Encoded download response is not supported")
            header_size = _header_length(response.headers)
            etag = response.headers.get("ETag")
            if status == 206:
                content_range = response.headers.get("Content-Range", "")
                match = re.fullmatch(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)", content_range)
                if not state or not match:
                    raise _DownloadProtocolError("Unexpected or invalid download Content-Range")
                start, end, total = map(int, match.groups())
                if (start != offset or end != total - 1 or start > end or total != state["total"]
                        or etag != state["etag"] or not _strong_etag(etag)
                        or (header_size is not None and header_size != end - start + 1)
                        or response.headers.get("Content-Type", "").lower().startswith("multipart/")):
                    raise _DownloadProtocolError("Inconsistent download range representation")
                response_size = end - start + 1
            elif status == 200:
                if response.headers.get("Content-Range") is not None:
                    raise _DownloadProtocolError("Content-Range on full download response")
                if expected_size is not None and header_size is not None and header_size != expected_size:
                    raise _DownloadProtocolError("Downloaded size mismatch in response headers")
                total = expected_size if expected_size is not None else header_size
                response_size = total
                _clear_download_state(target)
                state = None
                offset = 0
            else:
                raise _DownloadProtocolError(f"Unexpected download HTTP status: {status}")
            if total is not None and _strong_etag(etag):
                resumable = dict(identity, etag=etag, total=total)
            downloaded = offset
            transferred = 0
            started_at = time.monotonic()
            last_emit = 0.0
            _check_download_path(tmp)
            with tmp.open("ab" if offset else "wb") as file:
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    if response_size is not None and transferred + len(chunk) > response_size:
                        raise _DownloadProtocolError("Download response exceeds declared size")
                    file.write(chunk)
                    downloaded += len(chunk)
                    transferred += len(chunk)
                    now = time.monotonic()
                    if status_callback and (now - last_emit >= 0.5 or (total and downloaded >= total)):
                        last_emit = now
                        emit(status_callback, format_download_status(
                            downloaded, total, started_at=started_at, now=now,
                            label=label, item_index=item_index, item_count=item_count,
                            overall_done=overall_done, overall_total=overall_total,
                            transferred=transferred))
                file.flush()
                os.fsync(file.fileno())
            if response_size is not None and transferred != response_size:
                raise RuntimeError(f"Downloaded size mismatch for {label}: {downloaded} != {total}")
    except _DownloadProtocolError:
        _clear_download_state(target)
        raise
    except Exception:
        if resumable is not None:
            _save_download_state(target, resumable)
        elif state is None:
            _clear_download_state(target)
        raise
    _check_download_path(metadata)
    metadata.unlink(missing_ok=True)
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
    _check_download_path(Path(root or repo_root()) / artifact["install_path"])
    target = safe_install_path(artifact["install_path"], root)
    with _download_lock(target):
        return _install_artifact_to_target(
            artifact, target, status_callback, root, item_index, item_count,
            overall_done, overall_total)


def _install_artifact_to_target(
    artifact, target, status_callback, root, item_index, item_count, overall_done, overall_total,
):
    if artifact_ready(artifact, root):
        return target

    callback_failed = False
    original_callback = status_callback
    def guarded_callback(message):
        nonlocal callback_failed
        try:
            original_callback(message)
        except Exception:
            callback_failed = True
            raise
    if original_callback is not None:
        status_callback = guarded_callback

    url = artifact_url(artifact["repo_path"])
    label = Path(artifact["repo_path"]).name
    last_error = None
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        candidate_complete = False
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
                expected_sha256=artifact.get("sha256"),
            )
            candidate_complete = True
            emit(status_callback, f"Verifying models {label}")
            actual_hash = sha256_file(tmp)
            expected_hash = str(artifact.get("sha256") or "").lower()
            if expected_hash and actual_hash.lower() != expected_hash:
                _clear_download_state(target)
                raise RuntimeError(
                    f"SHA256 mismatch for {label}: {actual_hash.lower()} != {expected_hash}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            _install_download(tmp, target)
            return target
        except (HTTPError, URLError, TimeoutError, RuntimeError, OSError) as exc:
            if callback_failed:
                if candidate_complete:
                    _clear_download_state(target)
                raise
            last_error = exc
            if attempt >= DOWNLOAD_RETRIES:
                break
            emit(status_callback, f"Retrying models {label} ({attempt + 1}/{DOWNLOAD_RETRIES})")
            time.sleep(min(1.0 * attempt, 3.0))
    raise RuntimeError(f"Failed to download model artifact {label}: {last_error}")


def _download_asr_file(url, target, **kwargs):
    with _download_lock(target):
        _check_download_path(target)
        if model_file_ready(target):
            return
        tmp = download_url_to_file(url, target, **kwargs)
        _install_download(tmp, target)


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
    return all(model_file_ready(model_dir / name) for name in required)


def asr_openvino_model_ready():
    model_dir = asr_model_dir()
    required = ("config.json", "v3_ctc.onnx", "v3_vocab.txt")
    return all(model_file_ready(model_dir / name) for name in required)


def asr_openvino_artifact_model_ready(verify_hash=False):
    model_dir = repo_root() / "models" / "asr" / "gigaam-v3-ctc-openvino-int8-calib96"
    required = ("v3_ctc_bucket400_nncf_int8.xml", "v3_ctc_bucket400_nncf_int8.bin")
    if not all(model_file_ready(model_dir / name) for name in required) or not all(
        model_file_ready(asr_model_dir() / name) for name in ("config.json", "v3_vocab.txt")
    ):
        return False
    manifest = load_cached_artifact_manifest()
    if (manifest is not None and not valid_artifact_manifest(manifest)) or (manifest is None and artifact_manifest_cache_path().exists()):
        return False
    if manifest and artifacts_for_profile(manifest, ASR_OPENVINO_NNCF_INT8_PROFILE, "asr"):
        return profile_artifacts_ready(manifest, ASR_OPENVINO_NNCF_INT8_PROFILE, "asr", verify_hash=verify_hash)
    return True


def punct_model_ready(verify_hash=False):
    model_dir = punct_model_dir()
    required = ("config.json", "openvino_model.xml", "openvino_model.bin", "tokenizer.json")
    if not all(model_file_ready(model_dir / name) for name in required):
        return False
    manifest = load_cached_artifact_manifest()
    if (manifest is not None and not valid_artifact_manifest(manifest)) or (manifest is None and artifact_manifest_cache_path().exists()):
        return False
    if manifest and artifacts_for_profile(manifest, PUNCT_OPENVINO_FP16_PROFILE, "punctuation"):
        return profile_artifacts_ready(manifest, PUNCT_OPENVINO_FP16_PROFILE, "punctuation", verify_hash=verify_hash)
    return True


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
        if model_file_ready(target):
            downloaded_size += target.stat().st_size
            continue
        _download_asr_file(
            artifact_url(filename, repo_id=ASR_MODEL_REPO),
            target,
            status_callback=status_callback,
            label=filename,
            item_index=index,
            item_count=len(filenames),
            overall_done=downloaded_size,
            overall_total=total_size,
        )
        downloaded_size += target.stat().st_size

    if not asr_model_ready():
        import onnx_asr

        onnx_asr.load_model(ASR_MODEL_NAME, model_dir, quantization="int8")
    return asr_model_dir()


def ensure_asr_openvino_model(status_callback=None, profile_id=None):
    if profile_id == ASR_OPENVINO_NNCF_INT8_PROFILE:
        if asr_openvino_artifact_model_ready(verify_hash=True):
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
        if model_file_ready(target):
            downloaded_size += target.stat().st_size
            continue
        _download_asr_file(
            artifact_url(filename, repo_id=ASR_MODEL_REPO),
            target,
            status_callback=status_callback,
            label=filename,
            item_index=index,
            item_count=len(filenames),
            overall_done=downloaded_size,
        )
    return model_dir


def ensure_punct_model(status_callback=None, max_len=PUNCT_MAX_LEN):
    if punct_model_ready(verify_hash=True):
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
