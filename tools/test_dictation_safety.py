"""Deterministic delivery/lifecycle tests without UI, devices or real input."""
import os
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import voice_dictation_app as app


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


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SafetyTests))
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
