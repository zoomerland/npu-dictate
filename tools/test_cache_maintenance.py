"""Hermetic deferred-cache tests: temp roots, fake dialogs/widgets, no models."""
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cache_maintenance as maintenance


class CacheMaintenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cache-maintenance-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache = self.root / "models" / "openvino" / "cache"
        self.cache.mkdir(parents=True)
        self.marker = self.root / maintenance.STATE_NAME

    def file(self, name, data=b"compiled"):
        path = self.cache / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_explicit_schedule_idempotence_and_cancel_never_scan_cache(self):
        item = self.file("model.blob")
        with patch.object(maintenance.os, "scandir", side_effect=AssertionError("Scheduling cannot scan")):
            self.assertEqual(maintenance.read_state(self.root).state, "none")
            self.assertFalse(self.marker.exists())
            self.assertEqual(maintenance.cancel_clear(self.root).state, "none")
            self.assertFalse(self.marker.exists())
            self.assertEqual(maintenance.schedule_clear(self.root).state, "pending")
            saved = self.marker.read_bytes()
            with patch.object(maintenance, "_write", side_effect=AssertionError("No repeated write")):
                self.assertEqual(maintenance.schedule_clear(self.root).state, "pending")
            self.assertEqual(self.marker.read_bytes(), saved)
            self.assertNotIn(str(self.root), saved.decode())
            self.assertEqual(maintenance.cancel_clear(self.root).state, "cancelled")
            self.assertEqual(maintenance.cancel_clear(self.root).state, "cancelled")
        self.assertEqual(item.read_bytes(), b"compiled")
        with patch.object(maintenance, "_preflight", side_effect=AssertionError("Cancelled request")):
            self.assertEqual(maintenance.run_pending(self.root).state, "cancelled")

    def test_full_clear_only_cache_and_one_shot(self):
        self.file("a.blob")
        self.file("nested/deep/b.blob")
        protected = [self.root / "models" / "asr" / "weights.bin",
                     self.root / "models" / ".manifests" / "MANIFEST.json",
                     self.root / ".hf" / "private.bin", self.root / "settings.json"]
        for path in protected:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"immutable fixture")
        self.assertEqual(maintenance.schedule_clear(self.root).state, "pending")
        result = maintenance.run_pending(self.root)
        self.assertEqual(result, maintenance.CacheState("cleared", deleted_files=2, deleted_dirs=2))
        self.assertEqual(list(self.cache.iterdir()), [])
        self.assertEqual(maintenance.read_state(self.root), result)
        for path in protected:
            self.assertEqual(path.read_bytes(), b"immutable fixture")
        newly_compiled = self.file("next.blob")
        with patch.object(maintenance, "_preflight", side_effect=AssertionError("No auto repeat")):
            self.assertEqual(maintenance.run_pending(self.root), result)
        self.assertTrue(newly_compiled.exists())

    def test_no_request_missing_cache_and_empty_cache(self):
        item = self.file("existing.blob")
        with patch.object(maintenance, "_preflight", side_effect=AssertionError("No request")):
            self.assertEqual(maintenance.run_pending(self.root).state, "none")
        self.assertTrue(item.exists())
        item.unlink()
        maintenance.schedule_clear(self.root)
        self.assertEqual(maintenance.run_pending(self.root).state, "cleared")
        self.cache.rmdir()
        maintenance.schedule_clear(self.root)
        self.assertEqual(maintenance.run_pending(self.root).state, "missing")
        self.assertFalse(self.cache.exists())

    def test_fresh_absent_data_root_means_no_request_not_failure(self):
        fresh = self.root / "new-profile" / "data"
        with patch.object(maintenance, "_preflight", side_effect=AssertionError("No possible marker")), \
             patch.object(maintenance, "_write", side_effect=AssertionError("Do not create fresh data")):
            for action in (maintenance.read_state, maintenance.run_pending, maintenance.cancel_clear):
                self.assertEqual(action(fresh), maintenance.CacheState())
        self.assertFalse(fresh.parent.exists())
        self.assertEqual(maintenance.schedule_clear(fresh).reason, "state_io")
        self.assertFalse(fresh.parent.exists())

    def test_corrupt_empty_oversized_or_arbitrary_path_job_is_not_authority(self):
        item = self.file("safe.blob")
        maintenance.schedule_clear(self.root)
        valid = json.loads(self.marker.read_text())
        invalid = [b"", b"not json", b"x" * (maintenance.MAX_STATE_BYTES + 1),
                   json.dumps(dict(valid, path=str(self.cache))).encode(),
                   json.dumps(dict(valid, version=2)).encode(),
                   json.dumps(dict(valid, version=True)).encode(),
                   json.dumps(dict(valid, operation="remove_models")).encode(),
                   json.dumps(dict(valid, state=[])).encode(),
                   json.dumps(dict(valid, deleted_files=True)).encode(),
                   json.dumps(dict(valid, deleted_dirs=-1)).encode(),
                   json.dumps(dict(valid, reason="unknown")).encode(),
                   json.dumps(dict(valid, deleted_files=1)).encode(),
                   self.marker.read_bytes()[:-1] + b',"state":"pending"}',
                   b"[" * 1500 + b"]" * 1500]
        for raw in invalid:
            with self.subTest(raw=raw[:30]):
                self.marker.write_bytes(raw)
                with patch.object(maintenance, "_preflight", side_effect=AssertionError("Invalid authority")):
                    for action in (maintenance.run_pending, maintenance.schedule_clear, maintenance.cancel_clear):
                        result = action(self.root)
                        self.assertEqual(result.state, "failed")
                        self.assertEqual(result.reason, "invalid_state")
                self.assertEqual(self.marker.read_bytes(), raw)
                self.assertTrue(item.exists())

    def test_oversized_marker_is_not_opened(self):
        self.marker.write_bytes(b"x" * (maintenance.MAX_STATE_BYTES + 1))
        with patch.object(Path, "open", side_effect=AssertionError("Oversized marker read")):
            self.assertEqual(maintenance.run_pending(self.root).reason, "invalid_state")

    def test_fstat_ctime_difference_does_not_invalidate_same_marker(self):
        maintenance.schedule_clear(self.root)
        real = os.fstat
        def different_ctime(handle):
            info = real(handle)
            return SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino, st_size=info.st_size,
                                   st_mtime_ns=info.st_mtime_ns, st_ctime_ns=info.st_ctime_ns + 1)
        with patch.object(maintenance.os, "fstat", side_effect=different_ctime):
            self.assertEqual(maintenance.read_state(self.root).state, "pending")

    def test_relative_root_and_nonregular_marker_are_refused(self):
        with patch.object(Path, "lstat", side_effect=AssertionError("Relative root metadata")):
            self.assertEqual(maintenance.run_pending(Path("relative")).reason, "unsafe_path")
        self.marker.mkdir()
        self.assertEqual(maintenance.schedule_clear(self.root).reason, "unsafe_path")
        self.assertEqual(maintenance.run_pending(self.root).reason, "unsafe_path")

    def test_readonly_file_preflight_preserves_everything(self):
        first = self.file("a.blob")
        readonly = self.file("z.blob")
        readonly.chmod(0o444)
        self.addCleanup(lambda: readonly.chmod(0o666))
        maintenance.schedule_clear(self.root)
        result = maintenance.run_pending(self.root)
        self.assertEqual(result, maintenance.CacheState("failed", "readonly"))
        self.assertTrue(first.exists())
        self.assertTrue(readonly.exists())
        self.assertEqual(maintenance.run_pending(self.root), result)

    def test_unreadable_directory_preflight_preserves_everything(self):
        first = self.file("a.blob")
        second = self.file("nested/b.blob")
        maintenance.schedule_clear(self.root)
        real = os.scandir
        def unreadable(path):
            if Path(path).name == "nested":
                raise PermissionError("synthetic directory")
            return real(path)
        with patch.object(maintenance.os, "scandir", side_effect=unreadable):
            result = maintenance.run_pending(self.root)
        self.assertEqual(result, maintenance.CacheState("failed", "cache_io"))
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())

    def test_readonly_parent_directory_refuses_deletion(self):
        item = self.file("a.blob")
        maintenance.schedule_clear(self.root)
        real = Path.lstat
        readonly = SimpleNamespace(st_mode=stat.S_IFDIR | 0o555, st_file_attributes=0)
        with patch.object(Path, "lstat", lambda path: readonly if path == self.cache.parent else real(path)):
            self.assertEqual(maintenance.run_pending(self.root), maintenance.CacheState("failed", "readonly"))
        self.assertTrue(item.exists())

    def test_failed_cancel_keeps_pending_marker_and_never_inspects_cache(self):
        item = self.file("a.blob")
        maintenance.schedule_clear(self.root)
        original = self.marker.read_bytes()
        with patch.object(maintenance.os, "replace", side_effect=PermissionError("synthetic cancel write")), \
             patch.object(maintenance.os, "scandir", side_effect=AssertionError("Cancel never scans")):
            self.assertEqual(maintenance.cancel_clear(self.root), maintenance.CacheState("failed", "state_io"))
        self.assertEqual(self.marker.read_bytes(), original)
        self.assertTrue(item.exists())

    def test_nonregular_and_reparse_file_preflight_is_all_or_nothing(self):
        first = self.file("a.blob")
        special = self.file("z.blob")
        real = Path.lstat
        for mode, attributes in ((stat.S_IFIFO, 0), (stat.S_IFREG | 0o666, 0x400)):
            maintenance.schedule_clear(self.root)
            info = SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
            with patch.object(Path, "lstat", lambda path: info if path == special else real(path)):
                result = maintenance.run_pending(self.root)
            self.assertEqual(result, maintenance.CacheState("failed", "unsafe_path"))
            self.assertTrue(first.exists())
            self.assertTrue(special.exists())

    def test_bounded_preflight_never_starts_deletion(self):
        item = self.file("nested/deep/a.blob")
        for limits in ({"max_entries": 0}, {"max_depth": 0}, {"max_seconds": 0}):
            maintenance.schedule_clear(self.root)
            result = maintenance.run_pending(self.root, **limits)
            self.assertEqual(result, maintenance.CacheState("failed", "limit"))
            self.assertTrue(item.exists())

    def test_growth_race_before_unlink_is_refused(self):
        item = self.file("a.blob")
        maintenance.schedule_clear(self.root)
        original = maintenance._guard
        def grow(*args):
            item.write_bytes(b"grew during preflight")
            return original(*args)
        with patch.object(maintenance, "_guard", side_effect=grow):
            result = maintenance.run_pending(self.root)
        self.assertEqual(result, maintenance.CacheState("failed", "changed"))
        self.assertTrue(item.exists())

    def test_partial_unlink_failure_saved_and_never_automatically_retried(self):
        first, second = self.file("a.blob"), self.file("b.blob")
        maintenance.schedule_clear(self.root)
        real = Path.unlink
        def fail_second(path, *args, **kwargs):
            if path == second:
                raise PermissionError("synthetic file")
            return real(path, *args, **kwargs)
        with patch.object(Path, "unlink", fail_second):
            result = maintenance.run_pending(self.root)
        self.assertEqual(result, maintenance.CacheState("failed", "cache_io", deleted_files=1))
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())
        self.assertEqual(maintenance.read_state(self.root), result)
        with patch.object(maintenance, "_preflight", side_effect=AssertionError("No failure retry")):
            self.assertEqual(maintenance.run_pending(self.root), result)
        maintenance.schedule_clear(self.root)
        self.assertEqual(maintenance.run_pending(self.root).state, "cleared")

    def test_partial_rmdir_failure_is_reported(self):
        item = self.file("nested/a.blob")
        maintenance.schedule_clear(self.root)
        with patch.object(Path, "rmdir", side_effect=PermissionError("synthetic rmdir")):
            result = maintenance.run_pending(self.root)
        self.assertEqual(result, maintenance.CacheState("failed", "cache_io", deleted_files=1))
        self.assertFalse(item.exists())
        self.assertTrue(item.parent.exists())

    def test_new_root_file_after_deletion_is_preserved_and_not_cleared(self):
        first = self.file("a.blob")
        maintenance.schedule_clear(self.root)
        real = Path.unlink
        def arrival(path, *args, **kwargs):
            result = real(path, *args, **kwargs)
            if path == first:
                self.file("arrived.blob", b"new writer fixture")
            return result
        with patch.object(Path, "unlink", arrival):
            result = maintenance.run_pending(self.root)
        self.assertEqual(result, maintenance.CacheState("failed", "changed", deleted_files=1))
        self.assertEqual((self.cache / "arrived.blob").read_bytes(), b"new writer fixture")
        self.assertEqual(maintenance.read_state(self.root), result)

    def test_root_replacement_after_deletion_is_preserved_and_not_cleared(self):
        first = self.file("a.blob")
        maintenance.schedule_clear(self.root)
        real = Path.unlink
        def replace_root(path, *args, **kwargs):
            result = real(path, *args, **kwargs)
            if path == first:
                self.cache.rename(self.cache.with_name("previous-cache-fixture"))
                self.cache.mkdir()
                self.file("new.blob", b"replacement fixture")
            return result
        with patch.object(Path, "unlink", replace_root):
            result = maintenance.run_pending(self.root)
        self.assertEqual(result, maintenance.CacheState("failed", "changed", deleted_files=1))
        self.assertEqual((self.cache / "new.blob").read_bytes(), b"replacement fixture")

    def test_request_consumption_error_never_starts_purge(self):
        item = self.file("a.blob")
        maintenance.schedule_clear(self.root)
        with patch.object(maintenance.os, "replace", side_effect=PermissionError("synthetic state write")), \
             patch.object(maintenance, "_preflight", side_effect=AssertionError("Consumption must persist first")):
            result = maintenance.run_pending(self.root)
        self.assertEqual(result, maintenance.CacheState("failed", "state_io"))
        self.assertTrue(item.exists())
        self.assertEqual(maintenance.read_state(self.root).state, "pending")
        self.assertEqual(list(self.root.glob(".compiled-cache-maintenance-*.tmp")), [])

    def test_final_result_write_failure_leaves_running_no_purge_retry(self):
        self.file("a.blob")
        maintenance.schedule_clear(self.root)
        real = maintenance._write
        def fail_result(root, result, expected):
            if result.state == "cleared":
                raise PermissionError("synthetic result save")
            return real(root, result, expected)
        with patch.object(maintenance, "_write", side_effect=fail_result):
            result = maintenance.run_pending(self.root)
        self.assertEqual(result, maintenance.CacheState("failed", "state_io", deleted_files=1))
        self.assertEqual(maintenance.read_state(self.root).state, "running")
        with patch.object(maintenance, "_preflight", side_effect=AssertionError("No interrupted retry")):
            self.assertEqual(maintenance.run_pending(self.root).state, "running")

    def test_interruption_consumes_request_without_automatic_retry(self):
        item = self.file("a.blob")
        maintenance.schedule_clear(self.root)
        with patch.object(maintenance, "_preflight", side_effect=KeyboardInterrupt("synthetic interruption")):
            with self.assertRaises(KeyboardInterrupt):
                maintenance.run_pending(self.root)
        self.assertEqual(maintenance.read_state(self.root).state, "running")
        self.assertTrue(item.exists())
        self.assertTrue(maintenance.run_pending(self.root).needs_ack)

    def test_static_junction_or_symlink_confinement(self):
        outside = self.root / "outside"
        outside.mkdir()
        protected = outside / "private.blob"
        protected.write_bytes(b"private fixture")
        links = [self.cache / "redirect", self.cache, self.cache.parent]
        for link in links:
            with self.subTest(link=link.name):
                if link == self.cache:
                    self.cache.rmdir()
                elif link == self.cache.parent:
                    self.cache.rmdir()
                    self.cache.parent.rmdir()
                if os.name == "nt":
                    command = f"New-Item -ItemType Junction -Path '{link}' -Target '{outside}' | Out-Null"
                    process = subprocess.run(["pwsh", "-NoProfile", "-Command", command], capture_output=True, timeout=20)
                    self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
                else:
                    link.symlink_to(outside, target_is_directory=True)
                try:
                    maintenance.schedule_clear(self.root)
                    with patch.object(Path, "unlink", side_effect=AssertionError("No unlink after unsafe preflight")):
                        result = maintenance.run_pending(self.root)
                    self.assertEqual(result, maintenance.CacheState("failed", "unsafe_path"))
                    self.assertEqual(protected.read_bytes(), b"private fixture")
                    for action in (maintenance.read_state, maintenance.run_pending):
                        self.assertEqual(action(link / "absent-fresh-profile").reason, "unsafe_path")
                finally:
                    os.rmdir(link) if os.name == "nt" else link.unlink()
                    self.cache.mkdir(parents=True, exist_ok=True)


class CacheStartupTests(unittest.TestCase):
    def test_lock_then_maintenance_then_constructor_model_schedule(self):
        import voice_dictation_app as app
        order = []
        class Lock:
            acquired = True
            def __enter__(self):
                order.append("lock")
                return self
            def __exit__(self, *_args):
                order.append("release")
        result = maintenance.CacheState("cleared", deleted_files=2)
        def run_pending(root):
            self.assertEqual(root, Path("C:/temporary-fixture"))
            order.append("maintenance")
            return result
        def construct(**kwargs):
            self.assertEqual(kwargs["cache_maintenance_result"], result)
            order.append("constructor/model schedule")
            return SimpleNamespace(run=lambda: order.append("mainloop"))
        with patch.dict(os.environ, {"LOCAL_VOICE_DICTATION_SMOKE_IMPORT": "0"}), \
             patch.object(app, "SingleInstanceLock", return_value=Lock()), \
             patch.object(app, "user_data_root", return_value=Path("C:/temporary-fixture")), \
             patch.object(app.cache_maintenance, "run_pending", side_effect=run_pending), \
             patch.object(app, "VoiceDictationApp", side_effect=construct):
            self.assertEqual(app.main(), 0)
        self.assertEqual(order, ["lock", "maintenance", "constructor/model schedule", "mainloop", "release"])

    def test_smoke_secondary_instance_and_failed_lock_bypass_maintenance(self):
        import voice_dictation_app as app
        class Lock:
            acquired = False
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                pass
        forbidden = AssertionError("Maintenance is forbidden before acquired normal launch")
        with patch.object(app.cache_maintenance, "run_pending", side_effect=forbidden), \
             patch.object(app, "VoiceDictationApp", side_effect=forbidden), \
             patch.object(app, "SingleInstanceLock", return_value=Lock()), \
             patch.dict(os.environ, {"LOCAL_VOICE_DICTATION_SMOKE_IMPORT": "0"}):
            self.assertEqual(app.main(), 0)
            with patch.dict(os.environ, {"LOCAL_VOICE_DICTATION_SMOKE_IMPORT": "1"}), \
                 patch.object(app, "SingleInstanceLock", side_effect=forbidden):
                self.assertEqual(app.main(), 0)
            with patch.object(app, "SingleInstanceLock", side_effect=app.SingleInstanceInitializationError(5)), \
                 patch.object(app, "config_path", return_value=Path(os.environ["LOCAL_VOICE_DICTATION_DATA_ROOT"]) / "missing-fixture-config"), \
                 patch.object(app, "show_startup_error") as dialog:
                self.assertEqual(app.main(), 1)
                dialog.assert_called_once()

    def test_failed_maintenance_requires_ack_before_any_constructor(self):
        import voice_dictation_app as app
        lock = SimpleNamespace(acquired=True)
        class Context:
            def __enter__(self):
                return lock
            def __exit__(self, *_args):
                pass
        for result in (maintenance.CacheState("failed", "cache_io", deleted_files=1), maintenance.CacheState("running")):
            with self.subTest(state=result.state), \
                 patch.dict(os.environ, {"LOCAL_VOICE_DICTATION_SMOKE_IMPORT": "0"}), \
                 patch.object(app, "SingleInstanceLock", return_value=Context()), \
                 patch.object(app, "user_data_root", return_value=Path("C:/temporary-fixture")), \
                 patch.object(app.cache_maintenance, "run_pending", return_value=result), \
                 patch.object(app, "confirm_cache_startup", return_value=False) as confirm, \
                 patch.object(app, "VoiceDictationApp") as constructor:
                self.assertEqual(app.main(), 1)
                constructor.assert_not_called()
                confirm.assert_called_once_with(result)
                confirm.return_value = True
                self.assertEqual(app.main(), 0)
                constructor.assert_called_once_with(cache_maintenance_result=result)

    def test_startup_diagnostic_ru_en_and_default_no(self):
        import voice_dictation_app as app
        result = maintenance.CacheState("failed", "readonly", 1, 2)
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "settings.json"
            for language, expected in (("en", "read-only"), ("ru", "только для чтения")):
                config.write_text(json.dumps({"ui_language": language}), encoding="utf-8")
                with patch.object(app, "config_path", return_value=config), \
                     patch.object(app.messagebox, "askyesno", return_value=False) as dialog:
                    self.assertFalse(app.confirm_cache_startup(result))
                self.assertIn(expected, dialog.call_args.args[1])
                self.assertEqual(dialog.call_args.kwargs["default"], "no")
            with patch.object(app, "config_path", return_value=config), \
                 patch.object(app.messagebox, "askyesno", side_effect=app.tk.TclError("synthetic")), \
                 patch.object(app, "show_startup_error") as fallback:
                self.assertFalse(app.confirm_cache_startup(result))
                fallback.assert_called_once()


class CacheUiTests(unittest.TestCase):
    def test_real_settings_callbacks_confirmation_language_dirty_and_cancel(self):
        import voice_dictation_app as app
        from test_settings_ux import FakeWidget, FakeStyle, TracedValue, SettingsTests
        FakeWidget.widgets = []
        widgets = {name: type(name, (FakeWidget,), {}) for name in
                   ("Frame", "Label", "Button", "Checkbutton", "Radiobutton", "Combobox", "Entry", "Scale", "Notebook", "Scrollbar", "Progressbar")}
        fake_tk = SimpleNamespace(Toplevel=FakeWidget, Canvas=FakeWidget, StringVar=TracedValue,
                                 BooleanVar=TracedValue, DoubleVar=TracedValue, TclError=RuntimeError)
        fake_ttk = SimpleNamespace(Style=FakeStyle, **widgets)
        ui = SettingsTests().ui()
        ui.root, ui.last_text_var = FakeWidget(), TracedValue("fixture dictation")
        ui.cfg["input_device_index"] = None
        ui.engine.recording = False
        ui.settings_ui_scale = lambda: 1.5
        ui.monitor_workarea = lambda: (0, 0, 640, 440)
        ui.refresh_static_ui_text = ui.refresh_settings_window_text
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(app, "tk", fake_tk), patch.object(app, "ttk", fake_ttk), \
             patch.object(app, "is_startup_enabled", return_value=False), \
             patch.object(app, "input_devices", return_value=[]), \
             patch.object(app, "model_is_installed", return_value=True), \
             patch.object(app, "user_data_root", return_value=Path(temporary)), \
             patch.object(app.VoiceDictationApp, "_open_model_storage", lambda _self: None), \
             patch.object(app.VoiceDictationApp, "_open_model_availability", lambda _self: None), \
             patch.object(app, "save_config", lambda _cfg: None), \
             patch.object(app.messagebox, "askyesno", return_value=False) as dialog:
            root = Path(temporary)
            marker = root / maintenance.STATE_NAME
            cache_file = root / "models" / "openvino" / "cache" / "a.blob"
            cache_file.parent.mkdir(parents=True)
            cache_file.write_bytes(b"compiled fixture")
            ui.open_settings()
            self.assertFalse(marker.exists(), "Opening must not schedule")
            apply = next(w for w in FakeWidget.widgets if w.options.get("text") == "Apply")
            apply_settings = apply.options["command"].__closure__[0].cell_contents
            dirty = dict(zip(apply_settings.__code__.co_freevars,
                             (cell.cell_contents for cell in apply_settings.__closure__)))["dirty"]
            clear = next(w for w in FakeWidget.widgets if w.options.get("text") == "Schedule cache cleanup...")
            cancel = next(w for w in FakeWidget.widgets if w.options.get("text") == "Cancel scheduled cleanup")
            status = next(w.options["textvariable"] for w in FakeWidget.widgets
                          if "No cache cleanup scheduled" in getattr(w.options.get("textvariable"), "value", ""))
            clear.options["command"]()
            self.assertFalse(marker.exists(), "Declined confirmation")
            self.assertFalse(dirty.get())
            apply.options["command"]()
            self.assertFalse(marker.exists(), "Apply must not schedule")
            dialog.return_value = True
            clear.options["command"]()
            self.assertEqual(maintenance.read_state(root).state, "pending")
            self.assertEqual(clear.options["state"], "disabled")
            self.assertEqual(cancel.options["state"], "normal")
            self.assertFalse(dirty.get())
            self.assertTrue(cache_file.exists(), "Scheduling is never immediate purge")
            self.assertIn("next normal launch", status.get())
            language = next(w for w in FakeWidget.widgets if w.options.get("values") == list(app.UI_LANGUAGE_NAMES.values()))
            language.options["textvariable"].set("Русский")
            self.assertIn("следующий обычный запуск", status.get())
            self.assertEqual(clear.options["text"], "Запланировать очистку...")
            apply.options["command"]()
            self.assertFalse(dirty.get())
            with patch.object(maintenance.os, "replace", side_effect=PermissionError("synthetic UI cancel write")):
                cancel.options["command"]()
            self.assertEqual(maintenance.read_state(root).state, "pending")
            self.assertEqual(cancel.options["state"], "normal")
            self.assertIn("не удалось прочитать или сохранить", status.get())
            self.assertFalse(dirty.get())
            cancel.options["command"]()
            self.assertEqual(maintenance.read_state(root).state, "cancelled")
            self.assertFalse(dirty.get())
            self.assertIn("отменена", status.get())
            ui.cache_maintenance_result = maintenance.CacheState("failed", "readonly", 1, 2)
            ui.settings_refresh_cache()
            self.assertIn("только для чтения", status.get())
            self.assertFalse(dirty.get())
            clear.options["command"]()
            self.assertEqual(maintenance.read_state(root).state, "pending")
            save = next(w for w in FakeWidget.widgets if w.options.get("text") == "Сохранить")
            save.options["command"]()
            self.assertIsNone(ui.settings_refresh_cache)
            self.assertEqual(maintenance.read_state(root).state, "pending")
            self.assertTrue(cache_file.exists())
            ui.open_settings()
            self.assertEqual(ui.cache_maintenance_result.state, "pending")
            self.assertTrue(cache_file.exists())
            ui.settings_window.destroy()


if __name__ == "__main__":
    import sys
    from headless_ux_checks import main
    code = main(test_cases=(CacheMaintenanceTests, CacheStartupTests, CacheUiTests))
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
