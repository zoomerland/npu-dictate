"""Inventory distributable files without accepting application data or weights."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath


def checked_path(name):
    path = PurePosixPath(name.replace("\\", "/"))
    parts = tuple(part.casefold() for part in path.parts)
    if not parts or path.is_absolute() or ".." in parts or ":" in parts[0]:
        raise ValueError(f"Unsafe payload path: {name}")
    if any(part in {".hf", ".git", ".venv", "recordings", ".manifests", "hf_export"} for part in parts):
        raise ValueError(f"Private payload path: {name}")
    if any(part.startswith("compiled-cache-maintenance.json")
           or re.fullmatch(r"\.compiled-cache-maintenance-.*\.tmp(?:[.~].*)?", part)
           for part in parts):
        raise ValueError(f"Runtime maintenance payload path: {name}")
    for index, part in enumerate(parts):
        if part == "models" and parts[:index + 1] not in {
            ("_internal", "transformers", "models"), ("_internal", "onnx_asr", "models")
        }:
            raise ValueError(f"Model payload path: {name}")
        if part.startswith(("gigaam-v3", "rupunct_big")):
            raise ValueError(f"Model payload path: {name}")
    basename = parts[-1]
    if ((basename.startswith("voice_dictation_config") and basename != "voice_dictation_config.example.json")
            or basename.startswith("voice_dictation.log")
            or re.fullmatch(r"v3_ctc.*\.(onnx|xml|bin)", basename)
            or basename.endswith((".safetensors", ".gguf"))
            or (basename.startswith("pytorch_model") and basename.endswith(".bin"))
            or basename in {"openvino_model.xml", "openvino_model.bin", "flax_model.msgpack", "tf_model.h5"}):
        raise ValueError(f"Private/model payload file: {name}")
    return path.as_posix()


def digest_stream(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def inventory(app_dir=None, archive=None):
    files = []
    seen = set()
    def add(name, size, stream):
        name = checked_path(name)
        if name.casefold() in seen:
            raise ValueError(f"Duplicate payload file: {name}")
        seen.add(name.casefold())
        files.append(dict(path=name, size=size, sha256=digest_stream(stream)))
    if app_dir is not None:
        root = Path(app_dir)
        if not root.is_dir():
            raise ValueError("Application directory does not exist")
        if root.is_symlink() or (hasattr(root, "is_junction") and root.is_junction()):
            raise ValueError("Linked application directory is not a build output")
        for path in sorted(root.rglob("*")):
            name = checked_path(path.relative_to(root).as_posix())
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise ValueError(f"Linked payload path: {name}")
            if path.is_file():
                with path.open("rb") as stream:
                    add(name, path.stat().st_size, stream)
    else:
        with zipfile.ZipFile(archive) as zipped:
            for entry in zipped.infolist():
                checked_path(entry.filename)
                if entry.is_dir():
                    continue
                with zipped.open(entry) as stream:
                    add(entry.filename, entry.file_size, stream)
    if "npudictate.exe" not in seen:
        raise ValueError("Payload has no root NPUDictate.exe")
    return dict(schema_version=1, files=sorted(files, key=lambda item: item["path"]),
                total_bytes=sum(item["size"] for item in files))


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--app-dir")
    source.add_argument("--zip", dest="archive")
    parser.add_argument("--inventory-out")
    parser.add_argument("--compare")
    args = parser.parse_args()
    result = inventory(args.app_dir, args.archive)
    if args.compare and result != json.loads(Path(args.compare).read_text(encoding="utf-8-sig")):
        raise ValueError("Payload differs from the accepted build inventory")
    if args.inventory_out:
        Path(args.inventory_out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Payload PASS: {len(result['files'])} files, {result['total_bytes']} bytes")


if __name__ == "__main__":
    main()
