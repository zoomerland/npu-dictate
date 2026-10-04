"""Run deterministic UX regressions with real UI, input, models and network denied."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


def forbidden(*_args, **_kwargs):
    raise AssertionError("Real UI/input/model/network work is forbidden in this suite")


def main(test_cases=None):
    with tempfile.TemporaryDirectory(prefix="npu-dictate-ux-") as root, \
         patch.dict(os.environ, {"LOCAL_VOICE_DICTATION_DATA_ROOT": root}):
        import voice_dictation_app as app
        import model_setup
        from test_dictation_safety import SafetyTests
        from test_settings_ux import SettingsTests
        from test_model_readiness import ReadinessTests
        from test_rupunct_windows import PunctuationWindowTests
        from test_npu_preparation import PreparationTests
        from test_startup_support import StartupSupportTests
        from test_model_storage import StorageScanTests, StorageLifecycleTests, StorageUiTests
        from test_resumable_downloads import ResumableDownloadTests
        from test_frozen_smoke import FrozenSmokeTests
        import openvino as ov
        from test_offline_runtime import (
            BootstrapAstTests, GuardTests, PureTelemetryTests, RealImportTests,
        )

        patches = [patch.object(app, "sd", None), patch.object(app, "log_debug", lambda _message: None),
                   patch.object(model_setup, "urlopen", forbidden), patch.object(app.tk, "Tk", forbidden),
                   patch.object(app.tk, "Toplevel", forbidden), patch.object(app.pyperclip, "copy", forbidden),
                   patch.object(app.pyperclip, "paste", forbidden), patch.object(app.keyboard, "Controller", forbidden),
                   patch.object(app, "probe_openvino_hardware", forbidden),
                   patch.object(ov, "Core", forbidden)]
        for name in ("_load_asr_profile", "_load_punct_profile", "_get_vad", "ensure_audio_stream", "ensure_audio_stream_async", "send_ctrl_v", "send_enter"):
            patches.append(patch.object(app.DictationEngine, name, forbidden))
        from contextlib import ExitStack
        with ExitStack() as stack:
            for guard in patches:
                stack.enter_context(guard)
            suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(case)
                                       for case in (test_cases or (SafetyTests, SettingsTests, ReadinessTests,
                                                                  PunctuationWindowTests, PreparationTests,
                                                                  PureTelemetryTests, BootstrapAstTests,
                                                                  GuardTests, RealImportTests,
                                                                  StartupSupportTests, StorageScanTests,
                                                                  StorageLifecycleTests, StorageUiTests,
                                                                  ResumableDownloadTests, FrozenSmokeTests)))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
