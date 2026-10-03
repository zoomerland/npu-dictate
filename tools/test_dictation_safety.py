"""Deterministic delivery/lifecycle tests without UI, devices or real input."""
import os
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


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SafetyTests))
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if result.wasSuccessful() else 1)
