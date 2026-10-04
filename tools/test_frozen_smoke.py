"""Import-only diagnostics using fake modules, never a packaged process or UI."""
import os
import sys
import types
import unittest
from unittest.mock import patch

import frozen_smoke


class FrozenSmokeTests(unittest.TestCase):
    def setUp(self):
        self.stub = types.ModuleType("openvino.tools.ovc.telemetry_stub")
        self.utils = types.ModuleType("openvino.tools.ovc.telemetry_utils")
        self.utils.tm = self.stub
        ovc = types.ModuleType("openvino.tools.ovc")
        ovc.telemetry_stub, ovc.telemetry_utils = self.stub, self.utils
        self.modules = {"openvino_telemetry": None, "openvino.tools.ovc": ovc}

    def test_receipt_records_frozen_fallback(self):
        with patch.dict(sys.modules, self.modules), patch.object(sys, "frozen", True, create=True):
            self.assertEqual(frozen_smoke.offline_policy_receipt(), {
                "frozen": True, "optional_telemetry_blocked": True,
                "fallback": self.stub.__name__,
            })

    def test_missing_sentinel_loaded_root_or_child_rejected(self):
        with patch.dict(sys.modules, self.modules):
            del sys.modules["openvino_telemetry"]
            with self.assertRaises(RuntimeError):
                frozen_smoke.offline_policy_receipt()
        for modules in ({"openvino_telemetry": types.ModuleType("openvino_telemetry")},
                        {"openvino_telemetry.child": types.ModuleType("child")}):
            with patch.dict(sys.modules, {**self.modules, **modules}), self.assertRaises(RuntimeError):
                frozen_smoke.offline_policy_receipt()

    def test_vendor_fallback_mismatch_rejected(self):
        self.utils.tm = object()
        with patch.dict(sys.modules, self.modules), self.assertRaises(RuntimeError):
            frozen_smoke.offline_policy_receipt()

    def test_smoke_main_never_creates_app_or_instance_lock(self):
        import voice_dictation_app as app
        messages = []
        with patch.dict(os.environ, {"LOCAL_VOICE_DICTATION_SMOKE_IMPORT": "1"}), \
             patch.object(app, "VoiceDictationApp", side_effect=AssertionError("No UI")), \
             patch.object(app, "SingleInstanceLock", side_effect=AssertionError("No lock")), \
             patch.object(app, "log_debug", messages.append), \
             patch.object(frozen_smoke, "offline_policy_receipt", return_value={"synthetic": True}) as probe:
            self.assertEqual(app.main(), 0)
            self.assertEqual(messages[-1], "package smoke import ok")
            probe.side_effect = RuntimeError("synthetic policy failure")
            messages.clear()
            self.assertEqual(app.main(), 1)
            self.assertEqual(messages, ["package smoke import failed error=RuntimeError"])


if __name__ == "__main__":
    from headless_ux_checks import main
    code = main((FrozenSmokeTests,))
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
