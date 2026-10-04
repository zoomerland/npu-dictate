"""Block model checks deliberately while exercising the actual settings callbacks."""
import queue
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import model_availability
import voice_dictation_app as app
from test_settings_ux import FakeStyle, FakeWidget, SettingsTests, TracedValue, Value


class AvailabilityLifecycleTests(unittest.TestCase):
    def make(self, scanner):
        self.events = queue.Queue()
        self.now = 0.0
        controller = model_availability.ModelAvailabilityRefresh(self.events.put, scanner, clock=lambda: self.now)
        self.addCleanup(controller.close)
        return controller

    def complete(self, controller):
        _, generation, result = self.events.get(timeout=5)
        return controller.complete(generation, result)

    def test_one_worker_coalesces_requests_and_observes_interval(self):
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        calls = []
        def scanner(_cancel):
            calls.append(threading.get_ident())
            started.set()
            if not release.wait(5):
                raise AssertionError("test release timeout")
            return (("model", True),)
        controller = self.make(scanner)
        controller.open()
        self.assertTrue(started.wait(5))
        for _ in range(100):
            controller.request()
            controller.tick()
        self.assertEqual(len(calls), 1)
        release.set()
        self.assertTrue(self.complete(controller))
        self.assertEqual(controller.snapshot, {"model": True})
        controller.tick()
        self.assertEqual(len(calls), 1)
        self.now = 5.0
        controller.tick()
        self.assertTrue(self.complete(controller))
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(ident != threading.get_ident() for ident in calls))
        self.assertFalse(controller.pending)

    def test_close_reopen_discards_stale_without_overlapping_workers(self):
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        calls = []
        def scanner(cancel):
            calls.append(cancel)
            started.set()
            if not release.wait(5):
                raise AssertionError("test release timeout")
            return (("model", len(calls) == 2),)
        controller = self.make(scanner)
        controller.open()
        self.assertTrue(started.wait(5))
        controller.close()
        self.assertTrue(calls[0].is_set())
        controller.open()
        self.assertEqual(len(calls), 1)
        release.set()
        self.assertFalse(self.complete(controller))
        self.assertIsNone(controller.snapshot)
        controller.tick()
        self.assertTrue(self.complete(controller))
        self.assertEqual(controller.snapshot, {"model": True})
        self.assertFalse(controller.complete(controller.generation - 1, (("model", False),)))
        self.assertEqual(controller.snapshot, {"model": True})

    def test_failure_is_unknown_and_later_refresh_recovers(self):
        fail = {"value": True}
        def scanner(_cancel):
            if fail["value"]:
                raise OSError("synthetic")
            return (("model", False),)
        controller = self.make(scanner)
        controller.open()
        self.assertTrue(self.complete(controller))
        self.assertEqual(controller.snapshot, {})
        fail["value"] = False
        controller.request()
        self.now = 5.0
        controller.tick()
        self.assertTrue(self.complete(controller))
        self.assertEqual(controller.snapshot, {"model": False})

    def test_thread_start_failure_is_unknown_and_does_not_block(self):
        controller = self.make(lambda _cancel: (("model", True),))
        with patch.object(model_availability.threading, "Thread", side_effect=RuntimeError("synthetic")):
            controller.open()
        self.assertIsNone(controller.running)
        self.assertEqual(controller.snapshot, {})
        controller.request()
        self.now = 5.0
        controller.tick()
        self.assertTrue(self.complete(controller))
        self.assertEqual(controller.snapshot, {"model": True})


class SettingsResponsivenessTests(unittest.TestCase):
    @contextmanager
    def widgets_ui(self, scanner=app.scan_model_availability):
        FakeWidget.widgets = []
        types = {name: type(name, (FakeWidget,), {}) for name in
                 ("Frame", "Label", "Button", "Checkbutton", "Radiobutton", "Combobox", "Entry", "Scale", "Notebook", "Scrollbar", "Progressbar")}
        fake_ttk = SimpleNamespace(Style=FakeStyle, **types)
        fake_tk = SimpleNamespace(Toplevel=FakeWidget, Canvas=FakeWidget, StringVar=TracedValue,
                                 BooleanVar=TracedValue, DoubleVar=TracedValue, TclError=RuntimeError)
        ui = SettingsTests().ui()
        ui.root, ui.last_text_var = FakeWidget(), Value("")
        ui.root.after = lambda *_args: None
        ui.event_queue = queue.Queue()
        ui.engine.recording = False
        ui.settings_ui_scale = lambda: 1.0
        ui.monitor_workarea = lambda: (0, 0, 1280, 800)
        ui.model_availability = model_availability.ModelAvailabilityRefresh(ui.event_queue.put, scanner, clock=lambda: 0.0)
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(app, "tk", fake_tk), patch.object(app, "ttk", fake_ttk), \
             patch.object(app, "log_debug", lambda _message: None), \
             patch.object(app, "input_devices", return_value=[]), \
             patch.object(app, "is_startup_enabled", return_value=False), \
             patch.object(app, "user_data_root", return_value=Path(temporary)), \
             patch.object(app.VoiceDictationApp, "_open_model_storage", lambda _self: None), \
             patch.object(app, "save_config", side_effect=AssertionError("Background checks cannot save settings")):
            try:
                yield ui
            finally:
                ui.model_availability.close()

    def receive(self, ui):
        item = ui.event_queue.get(timeout=5)
        ui.event_queue.put(item)
        ui.poll_events()

    def dirty_value(self):
        button = next(w for w in reversed(FakeWidget.widgets) if w.options.get("text") == "Apply")
        apply = button.options["command"].__closure__[0].cell_contents
        values = dict(zip(apply.__code__.co_freevars, (cell.cell_contents for cell in apply.__closure__)))
        return values["dirty"]

    def model_combos(self):
        return [w for w in FakeWidget.widgets if w.winfo_exists() and
                any("GigaAM" in str(value) or "RUPunct" in str(value) for value in w.options.get("values", []))]

    def language_variable(self):
        return next(w.options["textvariable"] for w in reversed(FakeWidget.widgets)
                    if w.options.get("values") == list(app.UI_LANGUAGE_NAMES.values()))

    def test_settings_opens_while_checks_block_and_preserves_edits_and_language(self):
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        calls = []
        main_thread = threading.get_ident()
        def checker(_profiles, model_id, _default):
            self.assertNotEqual(threading.get_ident(), main_thread, "File checks ran on UI thread")
            calls.append(model_id)
            started.set()
            if not release.wait(5):
                raise AssertionError("test release timeout")
            return True
        with patch.object(app, "model_is_installed", side_effect=checker), self.widgets_ui() as ui:
            original_config = dict(ui.cfg)
            ui.open_settings()
            self.assertTrue(started.wait(5))
            self.assertFalse(release.is_set(), "Opening waited for checks")
            self.assertFalse(self.dirty_value().get())
            combos = self.model_combos()
            self.assertEqual(len(combos), 2)
            self.assertTrue(all("checking..." in w.options["textvariable"].get() for w in combos))
            selected_id = app.OPENVINO_ASR_MODEL
            combos[0].options["textvariable"].set(app.model_display_label(
                app.ASR_MODEL_PROFILES, selected_id, app.DEFAULT_ASR_MODEL, installed=None))
            self.language_variable().set("Русский")
            self.assertTrue(self.dirty_value().get())
            self.assertTrue(all("проверяется..." in w.options["textvariable"].get() for w in combos))
            ui.refresh_model_progress()
            release.set()
            self.receive(ui)
            expected = list(app.ASR_MODEL_PROFILES) + list(app.PUNCT_MODEL_PROFILES)
            self.assertEqual(calls, expected)
            self.assertTrue(all("скачано" in w.options["textvariable"].get() for w in combos))
            self.assertEqual(app.model_id_from_label(app.ASR_MODEL_PROFILES, combos[0].options["textvariable"].get(),
                                                   app.DEFAULT_ASR_MODEL), selected_id)
            self.assertTrue(self.dirty_value().get(), "Background completion lost unsaved edits")
            self.assertEqual(ui.cfg, original_config)

    def test_background_completion_does_not_dirty_settings(self):
        result = tuple((model_id, True) for profiles in (app.ASR_MODEL_PROFILES, app.PUNCT_MODEL_PROFILES)
                       for model_id in profiles)
        with self.widgets_ui(lambda _cancel: result) as ui:
            ui.cfg["input_device_index"] = 99
            original = dict(ui.cfg)
            ui.open_settings()
            self.receive(ui)
            self.assertFalse(self.dirty_value().get())
            self.assertEqual(ui.cfg, original)
            missing = f"{app.TRANSLATIONS['en']['missing_input']} (99)"
            microphone = next(w for w in FakeWidget.widgets if missing in w.options.get("values", []))
            self.assertEqual(microphone.options["textvariable"].get(), missing)

    def test_closed_window_and_old_generation_never_receive_results(self):
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        calls = []
        def scanner(cancel):
            calls.append(cancel)
            started.set()
            if not release.wait(5):
                raise AssertionError("test release timeout")
            return tuple((model_id, len(calls) == 2) for profiles in (app.ASR_MODEL_PROFILES, app.PUNCT_MODEL_PROFILES)
                         for model_id in profiles)
        with self.widgets_ui(scanner) as ui:
            ui.open_settings()
            self.assertTrue(started.wait(5))
            ui.settings_window.destroy()
            self.assertIsNone(ui.settings_refresh_models)
            self.assertTrue(calls[0].is_set())
            ui.open_settings()
            self.assertEqual(len(calls), 1)
            release.set()
            self.receive(ui)
            self.assertIsNone(ui.model_availability.snapshot)
            self.receive(ui)
            self.assertTrue(all(ui.model_availability.snapshot.values()))
            self.assertFalse(self.dirty_value().get())

    def test_unavailable_check_is_not_displayed_as_missing_download(self):
        def scanner(_cancel):
            raise OSError("synthetic")
        with self.widgets_ui(scanner) as ui:
            ui.open_settings()
            self.receive(ui)
            combos = self.model_combos()
            self.assertTrue(all("check unavailable" in w.options["textvariable"].get() for w in combos))
            self.assertTrue(all("needs download" not in w.options["textvariable"].get() for w in combos))
            self.language_variable().set("Русский")
            self.assertTrue(all("не удалось проверить" in w.options["textvariable"].get() for w in combos))

    def test_refresh_start_failure_replaces_old_labels_and_retry_recovers(self):
        result = tuple((model_id, True) for profiles in (app.ASR_MODEL_PROFILES, app.PUNCT_MODEL_PROFILES)
                       for model_id in profiles)
        with self.widgets_ui(lambda _cancel: result) as ui:
            ui.open_settings()
            self.receive(ui)
            combos = self.model_combos()
            self.assertTrue(all("downloaded" in w.options["textvariable"].get() for w in combos))
            ui.model_availability.clock = lambda: 5.0
            ui.model_availability.request()
            with patch.object(model_availability.threading, "Thread", side_effect=RuntimeError("synthetic")):
                ui.poll_events()
            self.assertTrue(all("check unavailable" in w.options["textvariable"].get() for w in combos))
            self.assertFalse(self.dirty_value().get())
            ui.model_availability.clock = lambda: 10.0
            ui.model_availability.request()
            ui.poll_events()
            self.receive(ui)
            self.assertTrue(all("downloaded" in w.options["textvariable"].get() for w in combos))
            self.assertFalse(self.dirty_value().get())

    def test_profile_failure_does_not_hide_other_results_or_repeat_checks(self):
        calls = []
        def checker(_profiles, model_id, _default):
            calls.append(model_id)
            if model_id == app.DEFAULT_ASR_MODEL:
                raise OSError("synthetic")
            return True
        with patch.object(app, "model_is_installed", side_effect=checker), patch.object(app, "log_debug", lambda _message: None):
            result = dict(app.scan_model_availability(threading.Event()))
        self.assertEqual(result[app.DEFAULT_ASR_MODEL], "unavailable")
        self.assertTrue(result[app.DEFAULT_PUNCT_MODEL])
        self.assertEqual(len(calls), len(result))


if __name__ == "__main__":
    import os
    import sys
    from headless_ux_checks import main
    code = main((AvailabilityLifecycleTests, SettingsResponsivenessTests))
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
