"""Bounded, read-only logical sizes for the app-local models tree."""
import os
import stat
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageSnapshot:
    model_bytes: int = 0
    cache_bytes: int = 0
    incomplete_bytes: int = 0
    state: str = "complete"
    issues: int = 0


def is_reparse(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _plain_directory(path):
    info = path.lstat()
    if is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise OSError("Not a plain directory")
    return info


def _fingerprint(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def scan_model_storage(root, cancel=None, *, max_entries=100000, max_seconds=10.0, max_depth=64):
    """Metadata only. Missing, skipped, changing or bounded trees are not exact zero.

    Refuse static links/reparse points, including root ancestors. This is a
    non-transactional snapshot, not an OS sandbox against adversarial path swaps.
    """
    root = Path(os.path.abspath(root))
    cancel = cancel or threading.Event()
    deadline = time.monotonic() + max_seconds
    totals = [0, 0, 0]
    issues = entries = 0

    def stopped():
        return cancel.is_set() or entries >= max_entries or time.monotonic() >= deadline

    def walk(directory, relative, depth):
        nonlocal issues, entries
        if stopped() or depth > max_depth:
            issues += 1
            return
        try:
            before = _plain_directory(directory)
            with os.scandir(directory) as children:
                for child in children:
                    if stopped():
                        issues += 1
                        break
                    entries += 1
                    parts = relative + (child.name.lower(),)
                    try:
                        path = directory / child.name
                        path.relative_to(root)
                        info = path.lstat()
                        if is_reparse(info):
                            issues += 1
                            continue
                        if stat.S_ISDIR(info.st_mode):
                            if child.name.lower() in {".hf", ".manifests"}:
                                continue
                            walk(path, parts, depth + 1)
                        elif stat.S_ISREG(info.st_mode):
                            name = child.name.lower()
                            if name.endswith((".download.json", ".download.meta.json",
                                              ".download.json.tmp", ".download.meta.json.tmp")):
                                continue
                            after = path.lstat()
                            if is_reparse(after) or _fingerprint(info) != _fingerprint(after):
                                issues += 1
                                continue
                            category = 2 if name.endswith(".download") else (1 if parts[:2] == ("openvino", "cache") else 0)
                            totals[category] += info.st_size
                        else:
                            issues += 1
                    except (OSError, ValueError):
                        issues += 1
            if _fingerprint(before) != _fingerprint(_plain_directory(directory)):
                issues += 1
        except OSError:
            issues += 1

    try:
        for path in [*reversed(root.parents), root]:
            if cancel.is_set() or time.monotonic() >= deadline:
                return StorageSnapshot(state="cancelled" if cancel.is_set() else "unavailable", issues=1)
            _plain_directory(path)
    except OSError:
        return StorageSnapshot(state="unavailable", issues=1)
    walk(root, (), 0)
    return StorageSnapshot(*totals, state="cancelled" if cancel.is_set() else ("partial" if issues else "complete"), issues=issues)


class StorageRefresh:
    """Main-thread lifecycle; workers only scan and enqueue immutable snapshots."""
    def __init__(self, publish, *, scanner=scan_model_storage, interval=5.0, clock=time.monotonic):
        self.publish, self.scanner, self.interval, self.clock = publish, scanner, interval, clock
        self.generation = 0
        self.active = self.pending = False
        self.running = None
        self.snapshot = None
        self.next_start = 0.0

    def open(self, root):
        self.close()
        self.root = Path(root)
        self.active = self.pending = True
        self.snapshot = None
        self.next_start = 0.0
        self.tick()

    def close(self):
        self.generation += 1
        self.active = self.pending = False
        if self.running:
            self.running[1].set()

    def request(self):
        if self.active:
            self.pending = True

    def tick(self):
        if not self.active or not self.pending or self.running or self.clock() < self.next_start:
            return
        generation, cancel, root = self.generation, threading.Event(), self.root
        self.running = (generation, cancel)
        self.pending = False
        self.next_start = self.clock() + self.interval
        scanner, publish = self.scanner, self.publish

        def work():
            try:
                result = scanner(root, cancel)
            except Exception:
                result = StorageSnapshot(state="unavailable", issues=1)
            publish(("model_storage", generation, result))

        try:
            threading.Thread(target=work, name="model-storage", daemon=True).start()
        except RuntimeError:
            self.running = None
            self.snapshot = StorageSnapshot(state="unavailable", issues=1)

    def complete(self, generation, snapshot):
        if not self.running or generation != self.running[0]:
            return False
        self.running = None
        if not self.active or generation != self.generation or snapshot.state == "cancelled":
            return False
        self.snapshot = snapshot
        return True
