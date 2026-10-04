"""Startup contracts using temporary files and a fake COM implementation only."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import app_paths
import voice_dictation_app as app
from test_settings_ux import SettingsTests


class StartupSupportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dictate-startup-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.install = self.root / "Installed app \u0414\u0438\u043a\u0442\u043e\u0432\u043a\u0430"
        self.install.mkdir()
        self.shortcut_path = self.root / "Programs" / "Startup" / "NPU Dictate.lnk"
        self.created = []
        self.failure = None
        self.messages = []
        client = ModuleType("comtypes.client")
        client.CreateObject = self.create_object
        comtypes = ModuleType("comtypes")
        comtypes.client = client
        guards = [
            patch.dict(sys.modules, {"comtypes": comtypes, "comtypes.client": client}),
            patch.object(app, "startup_folder", lambda: self.shortcut_path.parent),
            patch.object(app, "log_debug", self.messages.append),
            # Do not change global os.name: pathlib must retain its real OS flavor.
            patch.object(app, "os", SimpleNamespace(name="nt", close=os.close)),
            patch.object(sys, "frozen", False, create=True),
            patch.object(sys, "executable", str(self.install / "python.exe")),
            patch.dict(os.environ, {
                app_paths.APP_ROOT_ENV: str(self.install),
                app_paths.DATA_ROOT_ENV: str(self.root / "Redirected user data"),
            }),
        ]
        for guard in guards:
            guard.start()
            self.addCleanup(guard.stop)

    def create_object(self, name, dynamic):
        self.assertEqual((name, dynamic), ("WScript.Shell", True))
        if self.failure == "COM":
            raise OSError("synthetic COM failure")
        return SimpleNamespace(CreateShortcut=self.create_shortcut)

    def create_shortcut(self, name):
        path = Path(name)
        self.assertEqual(path.parent, self.shortcut_path.parent.parent)
        self.assertNotEqual(path.parent, self.shortcut_path.parent)
        self.assertEqual(path.suffix, ".lnk")
        if path.exists():
            raise OSError("Fake WSH rejects an existing invalid shortcut placeholder")
        if self.failure == "Create":
            raise OSError("synthetic CreateShortcut failure")
        shortcut = SimpleNamespace(path=path)

        def save():
            if self.failure == "empty":
                return
            path.write_bytes(b"partial" if self.failure == "Save" else b"saved shortcut")
            if self.failure == "Save":
                raise OSError("synthetic partial Save failure")

        shortcut.Save = save
        self.created.append(shortcut)
        return shortcut

    def seed_shortcut(self, content=b"previous valid shortcut"):
        self.shortcut_path.parent.mkdir(parents=True, exist_ok=True)
        self.shortcut_path.write_bytes(content)

    def temporary_shortcuts(self):
        return list(self.shortcut_path.parent.parent.glob(".NPU Dictate-*.lnk"))

    def test_frozen_target_arguments_and_install_working_directory(self):
        exe = self.install / "NPU Dictate.exe"
        with patch.object(sys, "frozen", True), patch.object(sys, "executable", str(exe)), \
             patch.object(Path, "replace", side_effect=AssertionError("Overwrite is forbidden")):
            self.assertEqual(app.startup_target_python(), exe)
            self.assertTrue(app.set_startup_enabled(True))
        shortcut = self.created[-1]
        self.assertEqual(shortcut.TargetPath, str(exe))
        self.assertEqual(shortcut.Arguments, "")
        self.assertEqual(shortcut.WorkingDirectory, str(self.install))
        self.assertNotEqual(shortcut.WorkingDirectory, str(app_paths.user_data_root()))
        self.assertEqual(shortcut.IconLocation, str(exe))
        self.assertEqual(shortcut.Description, app.APP_NAME)
        self.assertTrue(app.is_startup_enabled())
        self.assertEqual(self.temporary_shortcuts(), [])

    def test_frozen_without_app_root_override_uses_executable_parent(self):
        with patch.object(sys, "frozen", True), \
             patch.object(sys, "executable", str(self.install / "NPU Dictate.exe")):
            with patch.dict(os.environ):
                os.environ.pop(app_paths.APP_ROOT_ENV, None)
                self.assertTrue(app.set_startup_enabled(True))
        self.assertEqual(self.created[-1].WorkingDirectory, str(self.install))

    def test_source_pythonw_and_script_spaces_unicode(self):
        pythonw = self.install / ".venv" / "Scripts" / "pythonw.exe"
        pythonw.parent.mkdir(parents=True)
        pythonw.touch()
        self.assertEqual(app.startup_target_python(), pythonw)
        self.assertTrue(app.set_startup_enabled(True))
        shortcut = self.created[-1]
        self.assertEqual(shortcut.TargetPath, str(pythonw))
        self.assertEqual(shortcut.Arguments, f'"{self.install / "tools" / "voice_dictation_app.py"}"')
        self.assertEqual(shortcut.WorkingDirectory, str(self.install))

    def test_source_fallback_to_sys_executable(self):
        self.assertEqual(app.startup_target_python(), Path(sys.executable))
        self.assertTrue(app.set_startup_enabled(True))
        self.assertEqual(self.created[-1].TargetPath, sys.executable)

    def test_enable_disable_are_idempotent(self):
        self.assertTrue(app.set_startup_enabled(True))
        content = self.shortcut_path.read_bytes()
        self.assertTrue(app.set_startup_enabled(True))
        self.assertEqual(len(self.created), 1)
        self.assertEqual(self.shortcut_path.read_bytes(), content)
        self.assertTrue(app.set_startup_enabled(False))
        self.assertTrue(app.set_startup_enabled(False))
        self.assertFalse(app.is_startup_enabled())

    def test_existing_shortcut_is_not_rewritten_or_opened_with_com(self):
        self.seed_shortcut(b"unrelated or stale shortcut")
        self.failure = "COM"
        self.assertTrue(app.set_startup_enabled(True))
        self.assertEqual(self.shortcut_path.read_bytes(), b"unrelated or stale shortcut")
        self.assertEqual(self.created, [])

    def test_com_create_save_and_empty_save_fail_without_enabled_shortcut(self):
        for failure in ("COM", "Create", "Save", "empty"):
            with self.subTest(failure=failure):
                self.failure = failure
                self.assertFalse(app.set_startup_enabled(True))
                self.assertFalse(app.is_startup_enabled())
                self.assertEqual(self.temporary_shortcuts(), [])
                self.assertTrue(self.messages[-1].startswith("startup shortcut error="))

    def test_publish_failure_preserves_shortcut_appearing_during_save(self):
        def fail_rename(_source, destination):
            self.assertEqual(destination, self.shortcut_path)
            self.seed_shortcut()
            raise PermissionError("synthetic rename failure")

        with patch.object(Path, "rename", fail_rename):
            self.assertFalse(app.set_startup_enabled(True))
        self.assertEqual(self.shortcut_path.read_bytes(), b"previous valid shortcut")
        self.assertEqual(self.temporary_shortcuts(), [])

    def test_publish_failure_without_previous_shortcut_stays_disabled(self):
        with patch.object(Path, "rename", side_effect=PermissionError("synthetic")):
            self.assertFalse(app.set_startup_enabled(True))
        self.assertFalse(app.is_startup_enabled())
        self.assertEqual(self.temporary_shortcuts(), [])

    @unittest.skipUnless(os.name == "nt", "Windows no-overwrite rename contract")
    def test_concurrent_shortcut_creation_is_not_overwritten(self):
        original_create = self.create_shortcut

        def create_with_concurrent_save(name):
            shortcut = original_create(name)
            save = shortcut.Save

            def concurrent_save():
                save()
                self.seed_shortcut(b"concurrent unrelated shortcut")

            shortcut.Save = concurrent_save
            return shortcut

        with patch.object(self, "create_shortcut", create_with_concurrent_save):
            self.assertFalse(app.set_startup_enabled(True))
        self.assertEqual(self.shortcut_path.read_bytes(), b"concurrent unrelated shortcut")
        self.assertEqual(self.temporary_shortcuts(), [])

    def test_disable_unlink_failure_preserves_previous_shortcut(self):
        self.seed_shortcut()
        with patch.object(Path, "unlink", side_effect=PermissionError("synthetic")):
            self.assertFalse(app.set_startup_enabled(False))
        self.assertEqual(self.shortcut_path.read_bytes(), b"previous valid shortcut")

    def test_cleanup_failure_never_leaves_partial_link_in_startup(self):
        self.failure = "Save"
        original_unlink = Path.unlink

        def deny_partial_cleanup(path, *args, **kwargs):
            if path.exists() and path.read_bytes() == b"partial":
                raise PermissionError("synthetic cleanup")
            return original_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", deny_partial_cleanup):
            self.assertFalse(app.set_startup_enabled(True))
        self.assertFalse(app.is_startup_enabled())
        self.assertEqual(list(self.shortcut_path.parent.iterdir()), [])
        self.assertEqual(len(self.temporary_shortcuts()), 1)
        self.assertIn("startup shortcut cleanup error=PermissionError", self.messages)

    def test_placeholder_unlink_failure_is_reported_before_com_creation(self):
        with patch.object(Path, "unlink", side_effect=PermissionError("synthetic placeholder")):
            self.assertFalse(app.set_startup_enabled(True))
        self.assertEqual(self.created, [])
        self.assertFalse(app.is_startup_enabled())
        self.assertEqual(list(self.shortcut_path.parent.iterdir()), [])
        self.assertEqual(len(self.temporary_shortcuts()), 1)

    def test_fake_wsh_rejects_empty_existing_shortcut(self):
        self.shortcut_path.parent.parent.mkdir(parents=True)
        invalid = self.shortcut_path.parent.parent / ".NPU Dictate-invalid.lnk"
        invalid.touch()
        with self.assertRaisesRegex(OSError, "invalid shortcut placeholder"):
            self.create_shortcut(str(invalid))

    def test_mkdir_and_temp_creation_failure_are_reported(self):
        with patch.object(Path, "mkdir", side_effect=PermissionError("synthetic")):
            self.assertFalse(app.set_startup_enabled(True))
        self.shortcut_path.parent.mkdir(parents=True)
        with patch.object(tempfile, "mkstemp", side_effect=PermissionError("synthetic")):
            self.assertFalse(app.set_startup_enabled(True))
        self.assertFalse(app.is_startup_enabled())
        self.assertEqual(self.temporary_shortcuts(), [])

    def test_unsupported_os_does_not_resolve_startup_or_create_com(self):
        with patch.object(app, "os", SimpleNamespace(name="posix")), \
             patch.object(app, "startup_shortcut_path", side_effect=AssertionError("forbidden")):
            self.assertFalse(app.set_startup_enabled(True))
            self.assertFalse(app.set_startup_enabled(False))

    def test_startup_folder_appdata_and_home_fallback_are_pure(self):
        with patch.object(app, "os", os), \
             patch.object(app, "startup_folder", new=app_startup_folder):
            with patch.dict(os.environ, {"APPDATA": str(self.root / "Roaming")}):
                self.assertEqual(app.startup_folder(), self.root / "Roaming" / "Microsoft" /
                                 "Windows" / "Start Menu" / "Programs" / "Startup")
            with patch.dict(os.environ), patch.object(Path, "home", return_value=self.root):
                os.environ.pop("APPDATA", None)
                self.assertEqual(app.startup_folder(), self.root / "AppData" / "Roaming" /
                                 "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup")

    def test_settings_partial_save_failure_rolls_back_saved_and_active_config(self):
        ui = SettingsTests.ui(self)
        old = dict(ui.cfg)
        writes = []
        self.failure = "Save"
        with patch.object(app, "save_config", side_effect=lambda cfg: writes.append(dict(cfg))):
            self.assertFalse(ui.save_settings(None, dict(old, start_with_windows=True), close=False))
        self.assertEqual(writes, [dict(old, start_with_windows=True), old])
        self.assertEqual(ui.cfg, old)
        self.assertEqual(ui.applied_configs, [])
        self.assertFalse(app.is_startup_enabled())
        self.assertEqual(ui.settings_error_var.get(), "Startup error")

    def test_settings_disable_failure_preserves_shortcut_and_config(self):
        self.seed_shortcut()
        ui = SettingsTests.ui(self)
        ui.cfg["start_with_windows"] = True
        old = dict(ui.cfg)
        writes = []
        with patch.object(app, "save_config", side_effect=lambda cfg: writes.append(dict(cfg))), \
             patch.object(Path, "unlink", side_effect=PermissionError("synthetic")):
            self.assertFalse(ui.save_settings(None, dict(old, start_with_windows=False), close=False))
        self.assertEqual(writes, [dict(old, start_with_windows=False), old])
        self.assertEqual(ui.cfg, old)
        self.assertEqual(ui.applied_configs, [])
        self.assertEqual(self.shortcut_path.read_bytes(), b"previous valid shortcut")

    def test_settings_save_failure_never_attempts_startup_change(self):
        ui = SettingsTests.ui(self)
        old = dict(ui.cfg)
        with patch.object(app, "save_config", side_effect=PermissionError("synthetic")), \
             patch.object(app, "set_startup_enabled", side_effect=AssertionError("forbidden")):
            self.assertFalse(ui.save_settings(None, dict(old, start_with_windows=True), close=False))
        self.assertEqual(ui.cfg, old)
        self.assertFalse(app.is_startup_enabled())

    def test_settings_rollback_failure_reports_error_without_publishing_active_config(self):
        ui = SettingsTests.ui(self)
        old = dict(ui.cfg)
        self.failure = "Save"
        with patch.object(app, "save_config", side_effect=[None, PermissionError("synthetic")]):
            self.assertFalse(ui.save_settings(None, dict(old, start_with_windows=True), close=False))
        self.assertEqual(ui.cfg, old)
        self.assertEqual(ui.applied_configs, [])
        self.assertFalse(app.is_startup_enabled())
        self.assertEqual(ui.settings_error_var.get(), "Could not restore previous settings: PermissionError")


app_startup_folder = app.startup_folder


if __name__ == "__main__":
    from headless_ux_checks import main
    code = main(test_cases=(StartupSupportTests, SettingsTests))
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
