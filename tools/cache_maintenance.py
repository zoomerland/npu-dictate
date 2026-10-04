"""One-shot, deferred removal of the app-managed compiled-cache subtree only."""
import json
import os
import stat
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path


STATE_NAME = "compiled-cache-maintenance.json"
MAX_STATE_BYTES = 4096
OPERATION = "clear_compiled_cache"
STATES = {"pending", "running", "cleared", "missing", "cancelled", "failed"}
REASONS = {"", "unsafe_path", "readonly", "limit", "changed", "cache_io", "state_io", "invalid_state"}


@dataclass(frozen=True)
class CacheState:
    state: str = "none"
    reason: str = ""
    deleted_files: int = 0
    deleted_dirs: int = 0

    @property
    def needs_ack(self):
        return self.state in {"failed", "running"}


class MaintenanceError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _metadata(path, directory=False):
    info = path.lstat()
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if _linked(info) or not expected(info.st_mode):
        raise MaintenanceError("unsafe_path")
    return info


def _fingerprint(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _identity(info):
    return info.st_dev, info.st_ino


def _writable(path, info):
    if not info.st_mode & 0o222 or getattr(info, "st_file_attributes", 0) & 1 or not os.access(path, os.W_OK):
        raise MaintenanceError("readonly")


def _data_root(value, allow_missing=False):
    root = Path(value)
    if not root.is_absolute() or ".." in root.parts or root == Path(root.anchor):
        raise MaintenanceError("unsafe_path")
    root = Path(os.path.abspath(root))
    for parent in [*reversed(root.parents), root]:
        try:
            _metadata(parent, directory=True)
        except FileNotFoundError:
            if allow_missing:
                return None
            raise
    return root


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate state field")
        result[key] = value
    return result


def _read(root):
    path = root / STATE_NAME
    try:
        before = _metadata(path)
    except FileNotFoundError:
        return CacheState()
    if not 0 < before.st_size <= MAX_STATE_BYTES:
        raise MaintenanceError("invalid_state")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        # Windows fstat/lstat can disagree on ctime; compare their stable fields,
        # then use lstat-to-lstat for the full before/after change check below.
        if (_identity(opened), opened.st_size, opened.st_mtime_ns) != (_identity(before), before.st_size, before.st_mtime_ns):
            raise MaintenanceError("changed")
        raw = stream.read(MAX_STATE_BYTES + 1)
    if len(raw) > MAX_STATE_BYTES or _fingerprint(_metadata(path)) != _fingerprint(before):
        raise MaintenanceError("changed")
    try:
        document = json.loads(raw, object_pairs_hook=_unique_object)
        fields = {"version", "operation", "state", "reason", "deleted_files", "deleted_dirs"}
        if not isinstance(document, dict) or set(document) != fields:
            raise ValueError("schema")
        if type(document["version"]) is not int or document["version"] != 1 or document["operation"] != OPERATION:
            raise ValueError("operation")
        if document["state"] not in STATES or document["reason"] not in REASONS:
            raise ValueError("state")
        for key in ("deleted_files", "deleted_dirs"):
            if type(document[key]) is not int or not 0 <= document[key] <= 100000:
                raise ValueError("count")
        if document["state"] != "failed" and document["reason"]:
            raise ValueError("reason")
        if document["state"] in {"pending", "running", "cancelled", "missing"} and (document["deleted_files"] or document["deleted_dirs"]):
            raise ValueError("counts without purge")
        return CacheState(document["state"], document["reason"], document["deleted_files"], document["deleted_dirs"])
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise MaintenanceError("invalid_state") from None


def _write(root, result, expected):
    root = _data_root(root)
    _writable(root, _metadata(root, directory=True))
    if _read(root) != expected:
        raise MaintenanceError("changed")
    destination = root / STATE_NAME
    if expected.state != "none":
        _writable(destination, _metadata(destination))
    payload = {"version": 1, "operation": OPERATION, **asdict(result)}
    temporary = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=".compiled-cache-maintenance-", suffix=".tmp", dir=root)
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        _data_root(root)
        if _read(root) != expected:
            raise MaintenanceError("changed")
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink()


def _failure(error, files=0, dirs=0):
    return CacheState("failed", error.reason if isinstance(error, MaintenanceError) else "state_io", files, dirs)


def read_state(data_root):
    try:
        root = _data_root(data_root, allow_missing=True)
        return CacheState() if root is None else _read(root)
    except (OSError, MaintenanceError) as error:
        return _failure(error)


def schedule_clear(data_root):
    """Write only the marker, after explicit UI confirmation. Never inspect cache."""
    try:
        root = _data_root(data_root)
        previous = _read(root)
        if previous.state == "pending":
            return previous
        result = CacheState("pending")
        _write(root, result, previous)
        return result
    except (OSError, MaintenanceError) as error:
        return _failure(error)


def cancel_clear(data_root):
    """Cancel only a pending marker; never unlink any cache or model files."""
    try:
        root = _data_root(data_root, allow_missing=True)
        if root is None:
            return CacheState()
        previous = _read(root)
        if previous.state != "pending":
            return previous
        result = CacheState("cancelled")
        _write(root, result, previous)
        return result
    except (OSError, MaintenanceError) as error:
        return _failure(error)


def _preflight(root, deadline, max_entries, max_depth):
    target = root / "models" / "openvino" / "cache"
    directories = {root: _metadata(root, directory=True)}
    for part in (root / "models", root / "models" / "openvino", target):
        try:
            directories[part] = _metadata(part, directory=True)
            _writable(part, directories[part])
        except FileNotFoundError:
            return None
    files, pending, entries = [], [(target, 0)], 0
    while pending:
        directory, depth = pending.pop()
        if depth > max_depth or time.monotonic() >= deadline:
            raise MaintenanceError("limit")
        before = _metadata(directory, directory=True)
        if _identity(before) != _identity(directories[directory]):
            raise MaintenanceError("changed")
        _writable(directory, before)
        with os.scandir(directory) as children:
            for child in children:
                if entries >= max_entries or time.monotonic() >= deadline:
                    raise MaintenanceError("limit")
                entries += 1
                path = directory / child.name
                path.relative_to(target)
                info = path.lstat()
                if _linked(info):
                    raise MaintenanceError("unsafe_path")
                if stat.S_ISDIR(info.st_mode):
                    _writable(path, info)
                    directories[path] = info
                    pending.append((path, depth + 1))
                elif stat.S_ISREG(info.st_mode):
                    _writable(path, info)
                    files.append((path, info))
                else:
                    raise MaintenanceError("unsafe_path")
        if _fingerprint(before) != _fingerprint(_metadata(directory, directory=True)):
            raise MaintenanceError("changed")
    return target, directories, sorted(files, key=lambda entry: str(entry[0]))


def _guard(root, path, directories, deadline):
    if time.monotonic() >= deadline:
        raise MaintenanceError("limit")
    _data_root(root)
    for parent in reversed([path.parent, *path.parent.parents]):
        if parent == root or root in parent.parents:
            info = _metadata(parent, directory=True)
            if parent not in directories or _identity(info) != _identity(directories[parent]):
                raise MaintenanceError("changed")
            if parent == root / "models" / "openvino" / "cache" or root / "models" / "openvino" / "cache" in parent.parents:
                _writable(parent, info)


def _verify_empty(root, target, directories, deadline):
    _guard(root, target, directories, deadline)
    try:
        before = _metadata(target, directory=True)
        if _identity(before) != _identity(directories[target]):
            raise MaintenanceError("changed")
        _writable(target, before)
        with os.scandir(target) as children:
            if time.monotonic() >= deadline:
                raise MaintenanceError("limit")
            if next(children, None) is not None:
                raise MaintenanceError("changed")
        after = _metadata(target, directory=True)
        if _fingerprint(before) != _fingerprint(after):
            raise MaintenanceError("changed")
        _guard(root, target, directories, deadline)
    except FileNotFoundError:
        raise MaintenanceError("changed") from None


def run_pending(data_root, *, max_entries=20000, max_depth=32, max_seconds=10.0):
    """Call only after instance-lock acquisition, before model threads exist.

    The complete bounded list is preflighted before deletion. This is ordinary
    race detection, not a hostile same-user TOCTOU sandbox or atomic snapshot.
    A durable running marker consumes authorization before destructive work.
    """
    deleted_files = deleted_dirs = 0
    try:
        root = _data_root(data_root, allow_missing=True)
        if root is None:
            return CacheState()
        previous = _read(root)
        if previous.state != "pending":
            return previous
        running = CacheState("running")
        _write(root, running, previous)
    except (OSError, MaintenanceError) as error:
        return _failure(error)
    deadline = time.monotonic() + max_seconds
    try:
        inventory = _preflight(root, deadline, max_entries, max_depth)
        if inventory is None:
            result = CacheState("missing")
        else:
            target, directories, files = inventory
            for path, original in files:
                path.relative_to(target)
                _guard(root, path, directories, deadline)
                info = _metadata(path)
                _writable(path, info)
                if _fingerprint(info) != _fingerprint(original):
                    raise MaintenanceError("changed")
                path.unlink()
                deleted_files += 1
            nested = [path for path in directories if target in path.parents]
            for path in sorted(nested, key=lambda item: len(item.parts), reverse=True):
                path.relative_to(target)
                _guard(root, path, directories, deadline)
                info = _metadata(path, directory=True)
                _writable(path, info)
                if _identity(info) != _identity(directories[path]):
                    raise MaintenanceError("changed")
                path.rmdir()
                deleted_dirs += 1
            _verify_empty(root, target, directories, deadline)
            result = CacheState("cleared", deleted_files=deleted_files, deleted_dirs=deleted_dirs)
    except (OSError, MaintenanceError, ValueError) as error:
        reason = error.reason if isinstance(error, MaintenanceError) else "cache_io"
        result = CacheState("failed", reason, deleted_files, deleted_dirs)
    try:
        _write(root, result, running)
    except (OSError, MaintenanceError) as error:
        # The running marker still prevents another purge if result persistence
        # fails or this process is interrupted. Return the diagnostic to the UI.
        return _failure(error, deleted_files, deleted_dirs)
    return result
