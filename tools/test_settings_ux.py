"""Headless settings and presentation regressions with fake widgets/services."""
import os
import json
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
                                    is_idle=lambda: True, update_config=lambda cfg: ui.applied_configs.append(dict(cfg)),
                                    readiness_status=lambda: "Ready")
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

    def test_microphone_selection_never_silently_changes_device(self):
        devices = [dict(index=4, name="USB", hostapi="WASAPI", sample_rate=48000)]
        for language in ("en", "ru"):
            for current in (None, 4, 9):
                choices, selected = app.microphone_choices(devices, current, language)
                self.assertEqual(choices[selected], current)
                self.assertIn(None, choices.values())
            choices, selected = app.microphone_choices([], 9, language)
            self.assertEqual(choices[selected], 9)

    def test_unrelated_save_preserves_system_microphone(self):
        ui = self.ui()
        ui.cfg["input_device_index"] = None
        with patch.object(app, "save_config", lambda _cfg: None):
            self.assertTrue(ui.save_settings(None, dict(ui.cfg, overlay_size="large"), close=False))
        self.assertIsNone(ui.cfg["input_device_index"])

    def test_full_model_progress_and_readiness_refresh(self):
        ui = self.ui()
        ui.settings_model_progress_var = Value()
        states, refreshes = [], []
        ui.settings_model_progress_bar = SimpleNamespace(stop=lambda: None,
            configure=lambda **kwargs: states.append(kwargs), start=lambda _interval: states.append("start"))
        ui.settings_refresh_models = lambda: refreshes.append(True)
        status = "Downloading models 37%, 400 MB left, 2 MB/s, ETA 03:20, 1/4 model.bin"
        ui.model_load_status = status
        ui.refresh_model_progress()
        self.assertEqual(ui.settings_model_progress_var.get(), status)
        self.assertEqual(states[-1], dict(mode="determinate", value=37))
        ui.model_load_status = "Warming models"
        ui.refresh_model_progress()
        self.assertEqual(states[-1], "start")
        ui.model_load_status = "Ready"
        ui.refresh_model_progress()
        self.assertEqual(refreshes, [True])
        self.assertEqual(states[-1]["value"], 100)

    def test_save_does_not_hide_punctuation_failure(self):
        ui = self.ui()
        ui.engine.readiness_status = lambda: "Punctuation unavailable"
        with patch.object(app, "save_config", lambda _cfg: None):
            self.assertTrue(ui.save_settings(None, dict(ui.cfg), close=False))
        self.assertEqual(ui.statuses[-1], "Punctuation unavailable")

    def test_settings_geometry_fits_each_workarea_at_multiple_scales(self):
        for bounds in ((0, 0, 640, 440), (0, 0, 800, 560), (0, 0, 1024, 728),
                       (-1920, -300, 0, 740), (1280, 300, 2304, 1028)):
            for scale in (1.0, 1.5, 2.0):
                width, height, x, y = app.fit_settings_geometry(bounds, scale)
                left, top, right, bottom = bounds
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)
                self.assertGreaterEqual(x, left)
                self.assertGreaterEqual(y, top)
                self.assertLessEqual(x + width, right)
                self.assertLessEqual(y + height, bottom)

    def test_overlay_clamp_uses_one_monitor_workarea_not_virtual_gap(self):
        ui = self.ui()
        ui.monitor_workarea = lambda x, y: (1280, 300, 2304, 1028)
        self.assertEqual(ui.clamp_overlay_position(1100, -200, 160, 88), (1280, 300))
        self.assertEqual(ui.clamp_overlay_position(2400, 1200, 160, 88), (2144, 940))

    def test_single_column_rows_preserve_all_controls_without_collisions(self):
        class Grid:
            def __init__(self, row, column, span=1):
                self.info = dict(row=row, column=column, columnspan=span)
            def grid_info(self):
                return self.info.copy()
            def grid_configure(self, **kwargs):
                self.info.update(kwargs)
        widgets = [Grid(0, 0, 2), Grid(1, 0), Grid(1, 1), Grid(2, 1), Grid(3, 0, 2)]
        app.stack_settings_rows(widgets)
        self.assertEqual([widget.info["row"] for widget in widgets], list(range(5)))
        self.assertTrue(all(widget.info["column"] == 0 and widget.info["columnspan"] == 1 for widget in widgets))

    def test_diagnostics_do_not_read_or_copy_private_text_and_paths(self):
        ui = self.ui()
        ui.cfg.update(private_path="C:/Users/PRIVATE_PERSON/private", auth_token="PRIVATE_TOKEN")
        ui.current_status = "Error: C:/Users/PRIVATE_PERSON/private"
        ui.tray_icon = None
        ui.root = SimpleNamespace(state=lambda: "normal")
        ui.last_text_var = SimpleNamespace(get=lambda: self.fail("Dictation must not be read"))
        ui.engine.hardware_info["private_log"] = "PRIVATE_TEXT"
        with patch.object(app, "model_is_installed", return_value=True), \
             patch.object(app.Path, "read_text", side_effect=AssertionError("No log/config reads")):
            serialized = ui.collect_debug_info()
        for secret in ("PRIVATE_PERSON", "PRIVATE_TEXT", "PRIVATE_TOKEN", "log_tail", "last_text", "raw_status"):
            self.assertNotIn(secret, serialized)
        parsed = json.loads(serialized)
        self.assertEqual(parsed["status_phase"], "Error")
        self.assertEqual(parsed["config"]["asr_model"], ui.cfg["asr_model"])

    def test_russian_progress_translates_metrics_but_not_filenames(self):
        ui = self.ui()
        ui.cfg["ui_language"] = "ru"
        status = "Downloading models 37% 100.0 MB/270.0 MB, 170.0 MB left, 2.0 MB/s, ETA 01:25, 1/4 left_models.bin"
        translated = ui.localize_status(status)
        for token in ("170.0 МБ осталось", "2.0 МБ/с", "время 01:25", "left_models.bin"):
            self.assertIn(token, translated)
        self.assertEqual(ui.localize_status("Preparing model download 4 files"), "Подготовка загрузки моделей 4 файлов")
        self.assertEqual(ui.localize_status("First model setup: ASR, punctuation"), "Первичная загрузка моделей: распознавание, пунктуация")
        self.assertEqual(ui.localize_status("Verifying models left_models.bin"), "Проверка моделей left_models.bin")
        self.assertIn("2.0 МБ/с", ui.compact_download_status(status, translated))

    def test_translation_keys_and_startup_error_are_consistent(self):
        from string import Formatter
        self.assertEqual(set(app.TRANSLATIONS["en"]), set(app.TRANSLATIONS["ru"]))
        for key in app.TRANSLATIONS["en"]:
            fields = lambda value: {field for _literal, field, _spec, _convert in Formatter().parse(value) if field}
            self.assertEqual(fields(app.TRANSLATIONS["en"][key]), fields(app.TRANSLATIONS["ru"][key]), key)
        self.assertIn("Код ошибки Windows: 5", app.startup_lock_error_message(5, "ru"))
        self.assertIn("Windows error: 5", app.startup_lock_error_message(5, "en"))
        self.assertEqual(app.TRANSLATIONS["ru"]["overlay_opacity"], "Непрозрачность кнопки")


if __name__ == "__main__":
    import sys
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SettingsTests))
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
