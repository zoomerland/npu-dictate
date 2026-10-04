"""Temporary-tree and fake-UI storage regressions; no user models or GUI."""
import os
import queue
import stat
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import model_storage as storage


class StorageScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="model-storage-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "models"
        self.root.mkdir()

    def file(self, name, size):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
        return path

    def test_classification_metadata_only_and_hf_exclusion(self):
        self.file("asr/weights.bin", 11)
        self.file("openvino/punct/model.xml", 7)
        self.file("openvino/cache/nested/compiled.blob", 17)
        self.file("asr/weights.bin.download", 13)
        self.file("openvino/cache/build.download", 5)
        self.file("asr/weights.bin.download.json", 23)
        self.file("asr/other.download.meta.json", 29)
        self.file("asr/weights.bin.download.json.tmp", 43)
        self.file("openvino/cache/build.download.meta.json.tmp", 47)
        self.file("openvino/cache/build.download.json.tmp", 53)
        self.file(".manifests/manifest.json", 31)
        self.file(".hf/private.bin", 37)
        (self.base / ".hf").mkdir()
        (self.base / ".hf" / "private.bin").write_bytes(b"x" * 41)
        visited = []
        real = os.scandir
        def scandir(path):
            visited.append(str(path))
            return real(path)
        with patch.object(Path, "open", side_effect=AssertionError("No content reads")), \
             patch.object(storage.os, "scandir", side_effect=scandir):
            result = storage.scan_model_storage(self.root)
        self.assertEqual(result, storage.StorageSnapshot(18, 17, 18))
        self.assertFalse(any(".hf" in path or ".manifests" in path for path in visited))

    def test_missing_root_not_exact_zero_and_empty_root_is_exact(self):
        self.assertEqual(storage.scan_model_storage(self.root).state, "complete")
        self.assertEqual(storage.scan_model_storage(self.root / "absent").state, "unavailable")

    def test_unreadable_root_and_nested_directory(self):
        real_stat = Path.lstat
        def unreadable(path):
            if path == self.root:
                raise PermissionError("synthetic root")
            return real_stat(path)
        with patch.object(Path, "lstat", unreadable):
            self.assertEqual(storage.scan_model_storage(self.root).state, "unavailable")
        self.file("safe.bin", 5)
        self.file("denied/weight.bin", 7)
        real_scan = os.scandir
        def scandir(path):
            if Path(path).name == "denied":
                raise PermissionError("synthetic directory")
            return real_scan(path)
        with patch.object(storage.os, "scandir", side_effect=scandir):
            result = storage.scan_model_storage(self.root)
        self.assertEqual(result.state, "partial")
        self.assertEqual(result.model_bytes, 5)

    def test_permission_deleted_and_growing_files_are_partial(self):
        for problem in ("permission", "deleted", "growing"):
            with self.subTest(problem=problem):
                self.file("weight.bin", 7)
                real = Path.lstat
                calls = []
                def metadata(path):
                    if path.name != "weight.bin":
                        return real(path)
                    calls.append(path.name)
                    if problem == "permission":
                        raise PermissionError("synthetic")
                    if len(calls) == 2:
                        if problem == "deleted":
                            path.unlink()
                        else:
                            path.write_bytes(b"x" * 9)
                    return real(path)
                with patch.object(Path, "lstat", metadata):
                    result = storage.scan_model_storage(self.root)
                self.assertEqual(result.state, "partial")
                self.assertEqual(result.model_bytes, 0)
                self.assertGreater(result.issues, 0)

    def test_directory_changed_during_scan_is_partial(self):
        self.file("weight.bin", 7)
        real = Path.lstat
        calls = []
        def metadata(path):
            result = real(path)
            if path != self.root:
                return result
            calls.append(True)
            if len(calls) == 3:
                return SimpleNamespace(st_dev=result.st_dev, st_ino=result.st_ino,
                                       st_size=result.st_size, st_mtime_ns=result.st_mtime_ns + 1,
                                       st_ctime_ns=result.st_ctime_ns, st_mode=result.st_mode)
            return result
        with patch.object(Path, "lstat", metadata):
            self.assertEqual(storage.scan_model_storage(self.root).state, "partial")

    def test_limits_and_cancellation(self):
        self.file("nested/deep/weight.bin", 7)
        self.assertEqual(storage.scan_model_storage(self.root, max_depth=0).state, "partial")
        self.assertEqual(storage.scan_model_storage(self.root, max_entries=0).state, "partial")
        self.assertEqual(storage.scan_model_storage(self.root, max_seconds=0).state, "unavailable")
        cancel = threading.Event()
        cancel.set()
        self.assertEqual(storage.scan_model_storage(self.root, cancel).state, "cancelled")

    def test_reparse_attributes_are_rejected(self):
        info = SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)
        self.assertTrue(storage.is_reparse(info))
        self.file("weight.bin", 7)
        real = Path.lstat
        with patch.object(Path, "lstat", lambda path: info if path.name == "weight.bin" else real(path)):
            result = storage.scan_model_storage(self.root)
        self.assertEqual(result.state, "partial")
        self.assertEqual(result.model_bytes, 0)

    def test_native_link_root_and_ancestor_confinement(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "private.bin").write_bytes(b"private")
        link = self.root / "redirect"
        if os.name == "nt":
            # Junction creation needs no administrator rights. Cleanup unlinks
            # only this temporary reparse point, never its destination.
            command = f"New-Item -ItemType Junction -Path '{link}' -Target '{outside}' | Out-Null"
            result = subprocess.run(["pwsh", "-NoProfile", "-Command", command],
                                    capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        else:
            link.symlink_to(outside, target_is_directory=True)
        self.addCleanup(lambda: os.rmdir(link) if os.name == "nt" else link.unlink())
        self.file("safe.bin", 5)
        real = storage.os.scandir
        def confined(path):
            self.assertNotIn("redirect", str(path))
            self.assertNotIn("outside", str(path))
            return real(path)
        with patch.object(storage.os, "scandir", side_effect=confined):
            result = storage.scan_model_storage(self.root)
            self.assertEqual(result.model_bytes, 5)
            self.assertEqual(result.state, "partial")
            self.assertEqual(storage.scan_model_storage(link).state, "unavailable")
            self.assertEqual(storage.scan_model_storage(link / "nested").state, "unavailable")

class StorageLifecycleTests(unittest.TestCase):
    def make(self, scanner):
        self.events = queue.Queue()
        self.now = 0.0
        return storage.StorageRefresh(self.events.put, scanner=scanner, clock=lambda: self.now)

    def complete(self, controller):
        _, generation, result = self.events.get(timeout=5)
        return controller.complete(generation, result)

    def test_scan_off_ui_thread_and_requests_coalesced(self):
        calls = []
        main = threading.get_ident()
        def scanner(_root, _cancel):
            calls.append(threading.get_ident())
            return storage.StorageSnapshot(7)
        controller = self.make(scanner)
        controller.open("synthetic/models")
        for _ in range(1000):
            controller.request()
            controller.tick()
        self.assertTrue(self.complete(controller))
        self.assertEqual(len(calls), 1)
        controller.tick()
        self.assertEqual(len(calls), 1)
        self.now = 5.0
        controller.tick()
        self.assertTrue(self.complete(controller))
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(ident != main for ident in calls))
        self.assertFalse(controller.pending)

    def test_close_reopen_discards_stale_and_has_only_one_worker(self):
        started, release = threading.Event(), threading.Event()
        calls = []
        def scanner(_root, cancel):
            calls.append(cancel)
            started.set()
            if not release.wait(5):
                raise AssertionError("test release timeout")
            return storage.StorageSnapshot(len(calls))
        controller = self.make(scanner)
        self.addCleanup(release.set)
        controller.open("synthetic/models")
        self.assertTrue(started.wait(5))
        controller.close()
        self.assertTrue(calls[0].is_set())
        controller.open("synthetic/models")
        self.assertEqual(len(calls), 1)
        release.set()
        self.assertFalse(self.complete(controller))
        self.assertIsNone(controller.snapshot)
        controller.tick()
        self.assertTrue(self.complete(controller))
        self.assertEqual(controller.snapshot.model_bytes, 2)
        self.assertFalse(controller.complete(controller.generation - 1, storage.StorageSnapshot(999)))
        controller.close()
        controller.request()
        controller.tick()
        self.assertEqual(len(calls), 2)

    def test_worker_exception_is_unavailable(self):
        def scanner(_root, _cancel):
            raise PermissionError("synthetic")
        controller = self.make(scanner)
        controller.open("synthetic/models")
        self.assertTrue(self.complete(controller))
        self.assertEqual(controller.snapshot.state, "unavailable")


class StorageUiTests(unittest.TestCase):
    def test_actual_settings_storage_callbacks_relabel_cleanly_and_reopen(self):
        import voice_dictation_app as app
        from test_settings_ux import FakeWidget, FakeStyle, TracedValue, SettingsTests
        FakeWidget.widgets = []
        widgets = {name: type(name, (FakeWidget,), {}) for name in
                   ("Frame", "Label", "Button", "Checkbutton", "Radiobutton", "Combobox", "Entry", "Scale", "Notebook", "Scrollbar", "Progressbar")}
        class StorageCanvas(FakeWidget):
            def bind(self, event, callback, **kwargs):
                if callback.__name__ == "fit_content_width":
                    self.fit_content_width = callback
                super().bind(event, callback, **kwargs)
        fake_ttk = SimpleNamespace(Style=FakeStyle, **widgets)
        fake_tk = SimpleNamespace(Toplevel=FakeWidget, Canvas=StorageCanvas, StringVar=TracedValue,
                                 BooleanVar=TracedValue, DoubleVar=TracedValue, TclError=RuntimeError)
        ui = SettingsTests().ui()
        ui.root = FakeWidget()
        ui.last_text_var = TracedValue("Synthetic dictation")
        ui.root.after = lambda *_args: None
        ui.event_queue = queue.Queue()
        ui.cfg["input_device_index"] = None
        ui.engine.recording = False
        ui.settings_ui_scale = lambda: 1.5
        ui.monitor_workarea = lambda: (0, 0, 640, 440)
        ui.refresh_static_ui_text = ui.refresh_settings_window_text
        old_config = dict(ui.cfg)
        calls = []
        def scanner(root, _cancel):
            calls.append((root, threading.get_ident()))
            return storage.StorageSnapshot(1234, 56, 78)
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(app, "tk", fake_tk), patch.object(app, "ttk", fake_ttk), \
             patch.object(app, "input_devices", return_value=[]), \
             patch.object(app, "is_startup_enabled", return_value=False), \
             patch.object(app, "model_is_installed", return_value=True), \
             patch.object(app.VoiceDictationApp, "_open_model_availability", lambda _self: None), \
             patch.object(app, "user_data_root", return_value=Path(temporary)), \
             patch.object(app, "save_config", lambda _cfg: None):
            ui.model_storage = storage.StorageRefresh(ui.event_queue.put, scanner=scanner)
            ui.open_settings()
            def publish():
                item = ui.event_queue.get(timeout=5)
                ui.event_queue.put(item)
                ui.poll_events()
            publish()
            apply_button = next(w for w in FakeWidget.widgets if w.options.get("text") == "Apply")
            apply_settings = apply_button.options["command"].__closure__[0].cell_contents
            dirty = dict(zip(apply_settings.__code__.co_freevars,
                             (cell.cell_contents for cell in apply_settings.__closure__)))["dirty"]
            size_label = next(w for w in FakeWidget.widgets
                              if "Model files: 1 234" in getattr(w.options.get("textvariable"), "value", ""))
            refresh = next(w for w in FakeWidget.widgets if w.options.get("text") == "Refresh sizes")
            self.assertEqual(size_label.grid_info()["column"], 0)
            self.assertEqual(size_label.grid_info()["columnspan"], 1)
            model_rows = [w.grid_info()["row"] for w in size_label.master.children if w.grid_info()]
            self.assertEqual(len(model_rows), len(set(model_rows)))
            canvas = size_label.master.master
            canvas.fit_content_width(SimpleNamespace(width=240))
            self.assertEqual(size_label.options["wraplength"], 192)
            self.assertFalse(dirty.get())
            self.assertEqual(ui.cfg, old_config)
            refresh.options["command"]()
            self.assertFalse(dirty.get())
            self.assertIn("Refreshing", size_label.options["textvariable"].get())
            language = next(w for w in FakeWidget.widgets if w.options.get("values") == list(app.UI_LANGUAGE_NAMES.values()))
            language.options["textvariable"].set("Русский")
            self.assertIn("Файлы моделей: 1 234 байт", size_label.options["textvariable"].get())
            self.assertEqual(refresh.options["text"], "Обновить размеры")
            apply_button.options["command"]()
            self.assertFalse(dirty.get())
            ui.model_storage.snapshot = storage.StorageSnapshot(state="partial", issues=2)
            ui.refresh_model_storage()
            self.assertIn("Неполный снимок", size_label.options["textvariable"].get())
            self.assertFalse(dirty.get())
            ui.model_storage.snapshot = storage.StorageSnapshot(state="unavailable", issues=1)
            ui.refresh_model_storage()
            self.assertNotIn("0 байт", size_label.options["textvariable"].get())
            language.options["textvariable"].set("English")
            self.assertIn("Sizes unavailable", size_label.options["textvariable"].get())
            apply_button.options["command"]()
            save = next(w for w in FakeWidget.widgets if w.options.get("text") == "Save")
            save.options["command"]()
            self.assertFalse(ui.model_storage.active)
            self.assertIsNone(ui.settings_refresh_storage)
            ui.open_settings()
            publish()
            self.assertTrue(ui.model_storage.active)
            self.assertEqual(len(calls), 2)
            self.assertTrue(all(root == Path(temporary) / "models" for root, _ in calls))
            self.assertTrue(all(ident != threading.get_ident() for _, ident in calls))
            ui.settings_window.destroy()


if __name__ == "__main__":
    import sys
    from headless_ux_checks import main
    code = main((StorageScanTests, StorageLifecycleTests, StorageUiTests))
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
