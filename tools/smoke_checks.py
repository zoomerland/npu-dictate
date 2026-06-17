import argparse
import os
import subprocess
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import voice_dictation_app as app


class CheckRunner:
    def __init__(self):
        self.failures = []
        self.warnings = []

    def ok(self, message):
        print(f"[OK] {message}")

    def warn(self, message):
        self.warnings.append(message)
        print(f"[WARN] {message}")

    def fail(self, message):
        self.failures.append(message)
        print(f"[FAIL] {message}")

    def check(self, message, func):
        try:
            func()
            self.ok(message)
        except AssertionError as exc:
            detail = f": {exc}" if str(exc) else ""
            self.fail(f"{message}{detail}")
        except Exception as exc:
            self.fail(f"{message}: {type(exc).__name__}: {exc}")


def check_config_profiles():
    cfg = app.load_config()
    assert cfg["asr_model"] in app.ASR_MODEL_PROFILES
    assert cfg["punct_model"] in app.PUNCT_MODEL_PROFILES
    assert cfg["asr_device"] in app.ASR_MODEL_PROFILES[cfg["asr_model"]]["devices"]
    assert cfg["punct_device"] in app.PUNCT_MODEL_PROFILES[cfg["punct_model"]]["devices"]

    default_cfg = app.default_config()
    normalized = app.normalize_model_config(default_cfg)
    assert normalized["asr_model"] == app.DEFAULT_ASR_MODEL
    assert normalized["asr_device"] == "CPU"
    assert normalized["punct_device"] == "NPU"


def check_cpu_fallback_profile():
    cfg = app.default_config()
    cfg.update(
        {
            "asr_model": app.DEFAULT_ASR_MODEL,
            "asr_device": "CPU",
            "punct_model": app.DEFAULT_PUNCT_MODEL,
            "punct_device": "CPU",
            "use_punctuation": True,
        }
    )
    normalized = app.normalize_model_config(cfg)
    assert normalized["asr_device"] == "CPU"
    assert normalized["punct_device"] == "CPU"
    assert app.selected_openvino_devices(normalized) == ["CPU"]


def check_hardware_device_filtering():
    cpu_only_hardware = {"available": True, "devices": ["CPU"]}
    cfg = app.default_config()
    cfg.update(
        {
            "asr_model": app.OPENVINO_ASR_NNCF_INT8_MODEL,
            "asr_device": "NPU",
            "punct_model": app.DEFAULT_PUNCT_MODEL,
            "punct_device": "NPU",
            "use_punctuation": True,
        }
    )
    normalized = app.normalize_model_config(cfg, cpu_only_hardware)
    assert normalized["asr_device"] == "CPU"
    assert normalized["punct_device"] == "CPU"
    assert app.selected_openvino_devices(normalized, cpu_only_hardware) == ["CPU"]

    asr_profile = app.ASR_MODEL_PROFILES[app.OPENVINO_ASR_NNCF_INT8_MODEL]
    assert app.model_available_devices(asr_profile, cpu_only_hardware) == ("CPU",)


def check_openvino_probe():
    info = app.probe_openvino_hardware(app.load_config())
    assert "available" in info
    assert "selected_devices" in info
    assert isinstance(info["warnings"], list)
    if info["available"]:
        assert isinstance(info["devices"], list)
        assert info["devices"], "OpenVINO reported no devices"


def check_insertion_spacing():
    cases = [
        ("", "Привет.", True, "Привет. "),
        ("Привет", "мир.", True, " мир. "),
        ("Привет ", "мир.", True, "мир. "),
        ("Казнить нельзя", ", помиловать.", True, ", помиловать. "),
        ("Казнить нельзя", ". Помиловать.", True, ". Помиловать. "),
        ("(", "тест", True, "тест "),
        ("«", "тест", True, "тест "),
        ("слово-", "то", True, "то "),
        ("слово", "мир.", False, " мир."),
        ("слово", "— это тест.", True, " — это тест. "),
        ("слово ", "— это тест.", True, "— это тест. "),
    ]
    for context, inserted, append, expected in cases:
        actual = app.apply_insertion_spacing(inserted, context, append)
        assert actual == expected, f"{context!r} + {inserted!r}: {actual!r} != {expected!r}"


class FakeClipboard:
    def __init__(self, value):
        self.value = value

    def paste(self):
        return self.value

    def copy(self, value):
        self.value = value


class FakeUser32:
    def IsClipboardFormatAvailable(self, _format):
        return 1


class TestEngine(app.DictationEngine):
    def __init__(self, cfg, send_ok=True):
        super().__init__(cfg, lambda _status: None, lambda *_args: None)
        self.send_ok = send_ok

    def send_ctrl_v(self):
        return self.send_ok


class BrokenKeyboard:
    def press(self, _key):
        raise RuntimeError("keyboard unavailable")

    def release(self, _key):
        return None


def check_clipboard_paste_behavior():
    original_clipboard = app.pyperclip
    original_windll = app.ctypes.WinDLL
    try:
        app.ctypes.WinDLL = lambda *_args, **_kwargs: FakeUser32()

        app.pyperclip = FakeClipboard("old")
        engine = TestEngine({"restore_clipboard_after_paste": True}, send_ok=True)
        assert engine.paste_text("new") is True
        assert app.pyperclip.value == "old"

        app.pyperclip = FakeClipboard("old")
        engine = TestEngine({"restore_clipboard_after_paste": False}, send_ok=True)
        assert engine.paste_text("new") is True
        assert app.pyperclip.value == "new"

        app.pyperclip = FakeClipboard("old")
        engine = TestEngine({"restore_clipboard_after_paste": True}, send_ok=False)
        engine.keyboard = BrokenKeyboard()
        assert engine.paste_text("new") is False
        assert app.pyperclip.value == "new"
    finally:
        app.pyperclip = original_clipboard
        app.ctypes.WinDLL = original_windll


def check_model_paths(runner):
    asr_dir = app.asr_model_dir()
    punct_dir = app.default_punct_model_dir()
    if asr_dir.exists():
        runner.ok(f"ASR model directory exists: {asr_dir}")
    else:
        runner.warn(f"ASR model directory is missing: {asr_dir}")
    if punct_dir.exists():
        runner.ok(f"Punctuation model directory exists: {punct_dir}")
    else:
        runner.warn(f"Punctuation model directory is missing: {punct_dir}")


def check_rupunct_cpu(timeout_sec):
    code = (
        "import os, sys\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {str(TOOLS_DIR)!r})\n"
        "from rupunct_restore import RUPunctRestorer\n"
        "from voice_dictation_app import default_punct_model_dir, repo_root\n"
        "restorer = RUPunctRestorer(default_punct_model_dir(), 'CPU', "
        "cache_dir=repo_root() / 'models' / 'openvino' / 'cache')\n"
        "result = restorer.restore('привет мир как дела')\n"
        "assert result and 'Привет' in result, result\n"
        "print(result, flush=True)\n"
        "os._exit(0)\n"
    )
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=app.repo_root(),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert result.returncode == 0, (result.stdout + result.stderr).strip()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run local smoke checks for Local Voice Dictation.")
    parser.add_argument(
        "--skip-rupunct",
        action="store_true",
        help="Skip the optional RUPunct CPU smoke test.",
    )
    parser.add_argument(
        "--rupunct-timeout",
        type=float,
        default=90.0,
        help="Timeout in seconds for the optional RUPunct CPU child-process smoke test.",
    )
    args = parser.parse_args()

    runner = CheckRunner()
    runner.check("config and model profiles normalize", check_config_profiles)
    runner.check("CPU-only fallback profile normalizes", check_cpu_fallback_profile)
    runner.check("hardware device filtering falls back to CPU", check_hardware_device_filtering)
    runner.check("OpenVINO hardware probe runs", check_openvino_probe)
    runner.check("context-aware insertion spacing cases pass", check_insertion_spacing)
    runner.check("clipboard paste/restore behavior passes with mocks", check_clipboard_paste_behavior)
    check_model_paths(runner)

    if args.skip_rupunct:
        runner.warn("Skipping RUPunct CPU smoke test by request")
    elif not app.default_punct_model_dir().exists():
        runner.warn("Skipping RUPunct CPU smoke test because the model directory is missing")
    else:
        runner.check("RUPunct CPU smoke test", lambda: check_rupunct_cpu(args.rupunct_timeout))

    print()
    print(f"Smoke checks complete: failures={len(runner.failures)} warnings={len(runner.warnings)}")
    if runner.failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
