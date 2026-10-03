"""Deterministic delivery/lifecycle tests without UI, devices or real input."""
import os
import threading
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import voice_dictation_app as app
import model_setup


class MemoryClipboard:
    def __init__(self, value="old"):
        self.value = value

    def paste(self):
        return self.value

    def copy(self, value):
        self.value = value


class FakeKeyboard:
    def __init__(self):
        self.events = []

    def press(self, key):
        self.events.append(("press", key))

    def release(self, key):
        self.events.append(("release", key))


class FakeAsr:
    def recognize(self, _audio, **_kwargs):
        return "recognized text"


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.clipboard = MemoryClipboard()
        self.statuses, self.texts = [], []
        self.patches = [
            patch.object(app, "log_debug", lambda _message: None),
            patch.object(app, "sd", None),
            patch.object(app, "pyperclip", self.clipboard),
            patch.object(app.keyboard, "Controller", FakeKeyboard),
            patch.object(app.ctypes, "WinDLL", lambda *_a, **_kw: SimpleNamespace(IsClipboardFormatAvailable=lambda _format: 1)),
        ]
        def forbidden(*_args, **_kwargs):
            raise AssertionError("Real model/network/device work forbidden")
        for name in ("_load_asr_profile", "_load_punct_profile", "_get_vad", "ensure_audio_stream", "ensure_audio_stream_async"):
            self.patches.append(patch.object(app.DictationEngine, name, forbidden))
        self.patches.append(patch.object(model_setup, "urlopen", forbidden))
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def engine(self, **kwargs):
        cfg = app.default_config()
        cfg.update(asr_vad_segments=False, asr_retry_fragmented=False, use_context=False,
                   use_punctuation=False, append_space=False, auto_paste=True)
        engine = app.DictationEngine(cfg, self.statuses.append, lambda *args: self.texts.append(args), **kwargs)
        engine.send_ctrl_v = lambda: self.fail("No actual input is allowed")
        return engine

    def job(self, engine, punct=None):
        return app.RecordingJob(
            blocks=(np.zeros(16000, dtype=np.float32),), sample_rate=16000,
            cfg=dict(engine.cfg), asr=FakeAsr(), punct=punct, audio_callback_count=0,
            audio_callback_statuses=(), audio_first_callback_perf=None, audio_max_callback_gap=0.0,
            recording_pre_roll_sec=0.0, recording_cpu_start=None, recording_cpu_end=None,
            recording_wall_start=None, recording_wall_end=None, context="",
            suppress_enter_after_paste=False,
        )

    def test_failed_focus_keeps_text_without_any_input(self):
        for focus in (lambda: False, lambda: (_ for _ in ()).throw(RuntimeError("focus"))):
            engine = self.engine(focus_callback=focus)
            self.assertFalse(engine.paste_text("new"))
            self.assertEqual(self.clipboard.value, "new")
            self.assertEqual(engine.keyboard.events, [])
            self.assertTrue(engine.last_paste_copied)

    def test_unavailable_identity_does_not_send(self):
        engine = self.engine(focus_callback=lambda: True, target_identity_callback=lambda: None)
        self.assertFalse(engine.paste_text("new"))
        self.assertEqual(self.clipboard.value, "new")
        self.assertEqual(engine.keyboard.events, [])

    def test_identity_drift_before_send_does_not_send(self):
        identities = iter(((10, 20, 30), (11, 21, 31)))
        engine = self.engine(target_identity_callback=lambda: next(identities))
        self.assertFalse(engine.paste_text("new"))
        self.assertEqual(self.clipboard.value, "new")
        self.assertEqual(engine.keyboard.events, [])

    def test_window_identity_can_gain_field_identity(self):
        identities = iter(((10, 20, 30), (10, 20, 30, 40, 50)))
        engine = self.engine(target_identity_callback=lambda: next(identities))
        engine.send_ctrl_v = lambda: True
        self.assertTrue(engine.paste_text("new"))
        self.assertEqual(self.clipboard.value, "old")

    def test_failed_send_rechecks_target_before_keyboard_fallback(self):
        identities = iter(((10, 20, 30), (10, 20, 30), (11, 21, 31)))
        engine = self.engine(target_identity_callback=lambda: next(identities))
        engine.send_ctrl_v = lambda: False
        self.assertFalse(engine.paste_text("new"))
        self.assertEqual(engine.keyboard.events, [])
        self.assertEqual(self.clipboard.value, "new")

    def test_copy_failure_is_not_reported_as_copied(self):
        engine = self.engine()
        with patch.object(self.clipboard, "copy", side_effect=RuntimeError("clipboard")):
            self.assertFalse(engine.paste_text("new"))
        self.assertFalse(engine.last_paste_copied)

    def test_punct_load_failure_keeps_raw_across_successive_dictations(self):
        engine = self.engine()
        engine.cfg.update(use_punctuation=True, press_enter_after_paste=True)
        loads = []
        def fail_load(*_args):
            loads.append(1)
            raise RuntimeError("punctuation")
        engine._load_punct_profile = fail_load
        for _ in range(2):
            engine._transcribe_recording(self.job(engine))
            self.assertEqual(self.clipboard.value, "recognized text")
            self.assertEqual(self.statuses[-1], "Copied - punctuation unavailable")
        self.assertEqual(len(self.texts), 2)
        self.assertEqual(len(loads), 1)
        self.assertEqual(engine.keyboard.events, [])
        self.assertTrue(engine.transcription_done.is_set())

    def test_punct_restore_failure_keeps_raw_even_if_clipboard_fails(self):
        engine = self.engine()
        engine.cfg["use_punctuation"] = True
        punct = SimpleNamespace(restore=lambda _text: (_ for _ in ()).throw(RuntimeError("restore")))
        with patch.object(self.clipboard, "copy", side_effect=RuntimeError("clipboard")):
            engine._transcribe_recording(self.job(engine, punct))
        self.assertEqual(self.texts[0][1], "recognized text")
        self.assertEqual(self.statuses[-1], "Text ready - punctuation unavailable")
        self.assertEqual(engine.keyboard.events, [])

    def test_empty_punctuation_result_keeps_raw(self):
        engine = self.engine()
        engine.cfg["use_punctuation"] = True
        engine._transcribe_recording(self.job(engine, SimpleNamespace(restore=lambda _text: "")))
        self.assertEqual(self.texts[0][1], "recognized text")
        self.assertEqual(self.statuses[-1], "Copied - punctuation unavailable")

    def test_unusable_and_nonstring_punctuation_never_send(self):
        for context in ("", "Earlier words"):
            for value in (".", "", "  ", None, 123, b"text"):
                engine = self.engine()
                engine.cfg.update(use_punctuation=True, press_enter_after_paste=True)
                punct = SimpleNamespace(restore=lambda _text, value=value: value,
                                        restore_inserted=lambda *_args, value=value: value)
                job = replace(self.job(engine, punct), context=context)
                engine._transcribe_recording(job)
                self.assertEqual(self.texts[-1][1].strip(), "recognized text")
                self.assertEqual(self.statuses[-1], "Copied - punctuation unavailable")
                self.assertEqual(engine.keyboard.events, [])

    def test_ui_retry_reaches_loader_and_recovers_without_settings_change(self):
        engine = self.engine()
        engine.cfg["use_punctuation"] = True
        engine.loaded, engine.stream = True, object()
        done = threading.Event()
        engine.status_callback = lambda value: (self.statuses.append(value), done.set())
        engine._load_punct_profile = lambda *_args: (_ for _ in ()).throw(RuntimeError("punct"))
        engine.load_punct_async(engine.cfg)
        self.assertTrue(done.wait(3))
        self.assertEqual(self.statuses[-1], "Punctuation unavailable")
        ui = app.VoiceDictationApp.__new__(app.VoiceDictationApp)
        ui.engine, ui.cfg = engine, dict(engine.cfg)
        ui.update_status = self.statuses.append
        done.clear()
        engine._load_punct_profile = lambda *_args: object()
        ui.handle_action("retry_models")
        self.assertTrue(done.wait(3))
        self.assertEqual(engine.readiness_status(), "Ready")
        self.assertIsNone(engine.punct_error)

    def test_punct_preload_failure_is_visible_and_explicit_retry_recovers(self):
        engine = self.engine()
        engine.cfg["use_punctuation"] = True
        engine.loaded, engine.stream = True, object()
        done = threading.Event()
        statuses = []
        def status(value):
            statuses.append(value)
            done.set()
        engine.status_callback = status
        engine._load_punct_profile = lambda *_args: (_ for _ in ()).throw(RuntimeError("punct"))
        self.assertTrue(engine.load_punct_async(engine.cfg))
        self.assertTrue(done.wait(3))
        self.assertEqual(statuses[-1], "Punctuation unavailable")
        done.clear()
        punct = object()
        engine._load_punct_profile = lambda *_args: punct
        self.assertTrue(engine.load_punct_async(engine.cfg))
        self.assertTrue(done.wait(3))
        self.assertEqual(statuses[-1], "Ready")
        self.assertIs(engine.punct, punct)

    def test_punctuation_reenable_invalidates_failed_load(self):
        engine = self.engine()
        engine.punct_error = RuntimeError("old")
        preloads = []
        engine.load_punct_async = lambda cfg: preloads.append(dict(cfg))
        engine.update_config(dict(engine.cfg, use_punctuation=True))
        self.assertIsNone(engine.punct_error)
        self.assertEqual(len(preloads), 1)

    def test_model_and_audio_settings_are_rejected_during_recording(self):
        for mode in ("hold", "toggle"):
            engine = self.engine()
            engine.cfg.update(mode=mode, auto_paste=False)
            old_asr = FakeAsr()
            engine.loaded, engine.asr, engine.stream, engine.sample_rate = True, old_asr, object(), 16000
            engine.start_recording()
            self.assertTrue(engine.recording)
            engine.audio_blocks = [np.zeros((16000, 1), dtype=np.float32)]
            changed = dict(engine.cfg, asr_model=app.OPENVINO_ASR_MODEL, sample_rate=48000, channels=2)
            self.assertFalse(engine.update_config(changed))
            self.assertIs(engine.asr, old_asr)
            self.assertEqual(engine.cfg["sample_rate"], 0)
            # A closed stream must not erase the rate already owned by this recording.
            engine.sample_rate = None
            self.assertTrue(engine.stop_recording())
            self.assertTrue(engine.transcription_done.wait(3))
            self.assertEqual(self.texts[-1][1], "recognized text")
            self.assertEqual(self.texts[-1][2], 1.0)

    def test_settings_update_rejected_during_transcription(self):
        engine = self.engine()
        engine.transcribing = True
        old_cfg = dict(engine.cfg)
        self.assertFalse(engine.update_config(dict(old_cfg, sample_rate=48000)))
        self.assertEqual(engine.cfg, old_cfg)

    def test_old_audio_callbacks_are_ignored(self):
        engine = self.engine()
        engine.recording, engine.sample_rate = True, 16000
        engine._audio_generation = 2
        data = np.zeros((160, 1), dtype=np.float32)
        engine._audio_callback(data, 160, None, None, generation=1)
        self.assertEqual(engine.audio_blocks, [])
        engine._audio_callback(data, 160, None, None, generation=2)
        self.assertEqual(len(engine.audio_blocks), 1)

    def test_ui_apply_during_dictation_does_not_write_or_hide_recording(self):
        engine = self.engine()
        engine.recording = True
        ui = app.VoiceDictationApp.__new__(app.VoiceDictationApp)
        ui.engine, ui.cfg = engine, dict(engine.cfg, ui_language="en")
        error = []
        ui.settings_error_var = SimpleNamespace(set=error.append)
        ui.update_status = lambda _status: self.fail("Recording status must not be replaced")
        with patch.object(app, "save_config", side_effect=AssertionError("No persistence during recording")):
            self.assertFalse(ui.save_settings(None, dict(ui.cfg)))
        self.assertEqual(error[-1], "Finish dictation before applying settings")
        self.assertTrue(engine.recording)

    def test_background_status_preserves_recording_indicator(self):
        ui = app.VoiceDictationApp.__new__(app.VoiceDictationApp)
        ui.engine = self.engine()
        ui.engine.recording = True
        ui.cfg = dict(ui.engine.cfg, ui_language="en", press_enter_after_paste=True,
                      show_stop_without_enter_button=True)
        ui.current_status, ui.recording_started_at, ui.transcribing_started_at = "Recording", 1.0, None
        ui.set_display_status = lambda value: setattr(ui, "current_display_status", value)
        ui.schedule_status_tick = lambda: None
        ui.set_overlay_progress_running = lambda _running: None
        ui.apply_overlay_layout = lambda: None
        ui.draw_overlay = lambda: None
        for status in ("Settings saved", "Ready", "Loading punct", "Hotkey captured"):
            ui.update_status(status)
            self.assertEqual(ui.current_status, "Recording")
            self.assertEqual(ui.overlay_button_text, "REC")
            self.assertEqual(ui.recording_started_at, 1.0)
            self.assertTrue(ui.stop_without_enter_button_visible())


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SafetyTests))
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
