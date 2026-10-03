"""Headless settings and presentation regressions with fake widgets/services."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import voice_dictation_app as app


class Value:
    def __init__(self, value=""):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class SettingsTests(unittest.TestCase):
    def setUp(self):
        patches = [patch.object(app, "sd", None), patch.object(app, "log_debug", lambda _message: None),
                   patch.object(app, "is_startup_enabled", lambda: False)]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def ui(self):
        ui = app.VoiceDictationApp.__new__(app.VoiceDictationApp)
        ui.cfg = dict(app.default_config(), ui_language="en", start_with_windows=False)
        ui.settings_error_var = Value()
        ui.applied_configs, ui.statuses = [], []
        ui.engine = SimpleNamespace(hardware_info={"available": True, "devices": ["CPU", "NPU"]},
                                    is_idle=lambda: True, update_config=lambda cfg: ui.applied_configs.append(dict(cfg)))
        ui.hotkeys = SimpleNamespace(update_config=lambda _cfg: None)
        ui.update_status = ui.statuses.append
        for name in ("apply_overlay_layout", "apply_overlay_opacity", "_position_overlay", "refresh_static_ui_text"):
            setattr(ui, name, lambda: None)
        return ui

    def test_invalid_hotkey_tokens_are_rejected(self):
        for text in ("f99", "ctrl+garbage", "ctrl+shift+qwerty", "fn+f8"):
            self.assertFalse(app.parse_hotkey(text), text)
            ui = self.ui()
            with patch.object(app, "save_config", side_effect=AssertionError("Invalid settings must not persist")):
                self.assertFalse(ui.save_settings(None, dict(ui.cfg, dictation_hotkey=text), close=False))
            self.assertEqual(ui.settings_error_var.get(), "Bad hotkey")

    def test_supported_hotkeys_and_named_keys(self):
        for text in ("ctrl+shift+2", "f24", "a", "space", "ctrl+page_up", "alt+enter", "win+d"):
            self.assertTrue(app.parse_hotkey(text), text)
        event = SimpleNamespace(keysym="Prior", char="", keycode=0x21)
        self.assertEqual(app.tk_key_to_token(event), "page_up")

    def test_equal_and_subset_hotkeys_are_rejected(self):
        for dictation, overlay in (("f8", "f8"), ("f8", "ctrl+f8"), ("ctrl+f8", "f8")):
            ui = self.ui()
            values = dict(ui.cfg, dictation_hotkey=dictation, overlay_hotkey=overlay)
            with patch.object(app, "save_config", side_effect=AssertionError("Conflicts must not persist")):
                self.assertFalse(ui.save_settings(None, values, close=False))
            self.assertEqual(ui.statuses[-1], "Hotkey conflict")

    def test_legacy_conflict_dispatches_only_overlay(self):
        manager = app.HotkeyManager.__new__(app.HotkeyManager)
        manager.cfg = dict(mode="toggle", dictation_hotkey="f8", overlay_hotkey="ctrl+f8")
        manager.pressed = set()
        manager.dictation_down = manager.overlay_down = manager.suspended = False
        actions = []
        manager.dispatch = actions.append
        manager.on_press(app.keyboard.Key.ctrl)
        manager.on_press(app.keyboard.Key.f8)
        manager.on_press(app.keyboard.Key.f8)
        self.assertEqual(actions, ["toggle_overlay"])

    def test_save_failure_does_not_publish_new_config(self):
        ui = self.ui()
        old = dict(ui.cfg)
        with patch.object(app, "save_config", side_effect=PermissionError("synthetic")):
            self.assertFalse(ui.save_settings(None, dict(ui.cfg, ui_language="ru"), close=False))
        self.assertEqual(ui.cfg, old)
        self.assertEqual(ui.applied_configs, [])
        self.assertEqual(ui.settings_error_var.get(), "Could not save settings: PermissionError")

    def test_startup_failure_restores_previous_saved_config(self):
        ui = self.ui()
        old = dict(ui.cfg)
        writes = []
        with patch.object(app, "save_config", side_effect=lambda cfg: writes.append(dict(cfg))), \
             patch.object(app, "set_startup_enabled", return_value=False):
            self.assertFalse(ui.save_settings(None, dict(ui.cfg, start_with_windows=True), close=False))
        self.assertEqual(ui.cfg, old)
        self.assertEqual(writes[-1], old)
        self.assertEqual(len(writes), 2)
        self.assertEqual(ui.applied_configs, [])

    def test_save_success_publishes_after_persistence(self):
        ui = self.ui()
        old_language = ui.cfg["ui_language"]
        def persisted(cfg):
            self.assertEqual(ui.cfg["ui_language"], old_language)
            self.assertEqual(cfg["ui_language"], "ru")
        with patch.object(app, "save_config", side_effect=persisted):
            self.assertTrue(ui.save_settings(None, dict(ui.cfg, ui_language="ru"), close=False))
        self.assertEqual(ui.cfg["ui_language"], "ru")
        self.assertEqual(len(ui.applied_configs), 1)

    def test_save_failure_does_not_prevent_exit(self):
        ui = self.ui()
        ui.exit_requested = False
        closed = []
        ui._finalize_exit = lambda: closed.append(True)
        ui.hotkeys.stop = lambda: None
        ui.engine.request_shutdown = lambda: False
        with patch.object(app, "save_config", side_effect=PermissionError("synthetic")):
            ui.exit_app()
        self.assertEqual(closed, [True])


if __name__ == "__main__":
    import sys
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SettingsTests))
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
