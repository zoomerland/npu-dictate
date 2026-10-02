import argparse
import hashlib
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import voice_dictation_app as app
import app_paths
import model_setup


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
    assert normalized["press_enter_after_paste"] is False
    assert normalized["show_stop_without_enter_button"] is False

    default_cfg["show_stop_without_enter_button"] = 1
    normalized = app.normalize_model_config(default_cfg)
    assert normalized["show_stop_without_enter_button"] is True


def check_config_persistence_is_recoverable():
    original_replace = app.os.replace
    original_log_debug = app.log_debug
    messages = []
    app.log_debug = messages.append
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "voice_dictation_config.json"
            missing = app.load_config(path)
            assert missing["asr_model"] == app.DEFAULT_ASR_MODEL

            valid = app.default_config()
            valid["overlay_opacity"] = 0.37
            payload = json.dumps(valid, ensure_ascii=False).encode("utf-8")
            path.write_bytes(b"\xef\xbb\xbf" + payload)
            assert app.load_config(path)["overlay_opacity"] == 0.37

            path.write_text('{"overlay_opacity":', encoding="utf-8")
            assert app.load_config(path)["overlay_opacity"] == 1.0
            path.write_text("[]", encoding="utf-8")
            assert app.load_config(path)["overlay_opacity"] == 1.0
            path.write_bytes(b"\xff\xfeinvalid")
            assert app.load_config(path)["overlay_opacity"] == 1.0
            assert any("config load fallback" in message for message in messages)

            old_cfg = app.default_config()
            old_cfg["overlay_opacity"] = 0.55
            app.save_config(old_cfg, path)
            old_bytes = path.read_bytes()

            def fail_replace(_source, _target):
                raise OSError("replace failed")

            app.os.replace = fail_replace
            new_cfg = dict(old_cfg)
            new_cfg["overlay_opacity"] = 0.88
            try:
                app.save_config(new_cfg, path)
            except OSError:
                pass
            else:
                raise AssertionError("atomic config write failure was not raised")
            assert path.read_bytes() == old_bytes
            assert not list(path.parent.glob(f".{path.name}.*.tmp"))

            app.os.replace = original_replace
            app.save_config(new_cfg, path)
            assert app.load_config(path)["overlay_opacity"] == 0.88
    finally:
        app.os.replace = original_replace
        app.log_debug = original_log_debug


def check_app_and_data_roots_are_separate():
    original_app_root = os.environ.get(app_paths.APP_ROOT_ENV)
    original_data_root = os.environ.get(app_paths.DATA_ROOT_ENV)
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            install_root = (root / "install").resolve()
            data_root = (root / "data").resolve()
            install_root.mkdir()
            data_root.mkdir()

            os.environ[app_paths.APP_ROOT_ENV] = str(install_root)
            os.environ.pop(app_paths.DATA_ROOT_ENV, None)
            assert app_paths.app_root() == install_root
            assert app_paths.user_data_root() == install_root

            os.environ[app_paths.DATA_ROOT_ENV] = str(data_root)
            assert app_paths.app_root() == install_root
            assert app_paths.user_data_root() == data_root
            assert app.repo_root() == data_root
            assert app.config_path() == data_root / "voice_dictation_config.json"
            assert app.asr_model_dir() == data_root / "models" / "asr" / "gigaam-v3-ctc"
            assert app.default_punct_model_dir() == (
                data_root / "models" / "openvino" / "RUPunct_big_fp16_static128"
            )
            assert app.debug_dictation_dir() == data_root / "recordings" / "debug_dictation"
            assert model_setup.repo_root() == data_root
            assert model_setup.hf_cache_dir() == data_root / ".hf"
            assert model_setup.artifact_manifest_cache_path() == (
                data_root
                / "models"
                / ".manifests"
                / "local-voice-dictation-openvino"
                / "MANIFEST.json"
            )

            pythonw = install_root / ".venv" / "Scripts" / "pythonw.exe"
            pythonw.parent.mkdir(parents=True)
            pythonw.touch()
            assert app.startup_target_python() == pythonw
    finally:
        if original_app_root is None:
            os.environ.pop(app_paths.APP_ROOT_ENV, None)
        else:
            os.environ[app_paths.APP_ROOT_ENV] = original_app_root
        if original_data_root is None:
            os.environ.pop(app_paths.DATA_ROOT_ENV, None)
        else:
            os.environ[app_paths.DATA_ROOT_ENV] = original_data_root


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


def check_model_display_labels():
    label = app.model_display_label(app.ASR_MODEL_PROFILES, app.DEFAULT_ASR_MODEL, app.DEFAULT_ASR_MODEL, "en")
    assert "Russian" in label
    assert "speech" in label
    assert "CPU" in label
    assert app.model_id_from_label(app.ASR_MODEL_PROFILES, label, app.DEFAULT_ASR_MODEL) == app.DEFAULT_ASR_MODEL

    ru_label = app.model_display_label(
        app.PUNCT_MODEL_PROFILES,
        app.DEFAULT_PUNCT_MODEL,
        app.DEFAULT_PUNCT_MODEL,
        "ru",
    )
    assert "русский" in ru_label
    assert "пунктуация" in ru_label
    assert app.model_id_from_label(app.PUNCT_MODEL_PROFILES, ru_label, app.DEFAULT_PUNCT_MODEL) == app.DEFAULT_PUNCT_MODEL


def check_download_status_format():
    status = model_setup.format_download_status(
        512 * 1024,
        1024 * 1024,
        started_at=1.0,
        now=2.0,
        label="model.bin",
        item_index=2,
        item_count=5,
        overall_done=1024 * 1024,
        overall_total=2 * 1024 * 1024,
    )
    assert status.startswith("Downloading models 75%")
    assert "1.5 MB/2.0 MB" in status
    assert "512.0 KB left" in status
    assert "512.0 KB/s" in status
    assert "ETA" in status
    assert "2/5 model.bin" in status
    assert app.status_percent(status) == 75
    assert app.status_percent("Loading ASR") is None


class FakeWarmupAsr:
    def __init__(self):
        self.called = False
        self.bucket_frames = (400,)

    def warmup(self, _buckets):
        self.called = True
        raise AssertionError("NPU ASR warmup should be skipped")


class FakePunct:
    def __init__(self):
        self.called = False

    def restore(self, _text):
        self.called = True
        return _text


def check_npu_asr_warmup_is_skipped():
    engine = app.DictationEngine(app.default_config(), lambda _status: None, lambda *_args: None)
    asr = FakeWarmupAsr()
    punct = FakePunct()
    cfg = app.default_config()
    cfg.update({"warmup_models": True, "asr_device": "NPU", "punct_device": "NPU"})
    engine._warmup_models(asr, punct, cfg)
    assert not asr.called
    assert punct.called


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


def check_leading_punctuation_removal():
    cases = [
        ("- Начало фразы", "", "Начало фразы"),
        ("...: «Начало фразы»", "", "«Начало фразы»"),
        ("— (Текст)", "", "(Текст)"),
        ("?!…", "", ""),
        ("  :\tТекст", "", "Текст"),
        ("123: начало", "", "123: начало"),
        ("- контекст неизвестен", None, "- контекст неизвестен"),
        (", помиловать.", "Казнить нельзя", ", помиловать."),
        ("— это уточнение", "Начало", "— это уточнение"),
    ]
    for source, context, expected in cases:
        actual = app.strip_leading_punctuation(source, context)
        assert actual == expected, f"{context!r} + {source!r}: {actual!r} != {expected!r}"


def check_post_paste_statuses():
    cases = [
        (False, False, None, None, "Pasted"),
        (True, True, None, None, "Pasted without Enter"),
        (True, False, True, None, "Pasted + Enter"),
        (True, False, False, "target_changed", "Pasted - Enter skipped"),
        (True, False, False, "target_unavailable", "Pasted - Enter skipped"),
        (True, False, False, "send_failed", "Pasted - Enter failed"),
    ]
    for press_enter, suppress_enter, enter_sent, reason, expected in cases:
        actual = app.pasted_status(press_enter, suppress_enter, enter_sent, reason)
        assert actual == expected, f"{press_enter}, {suppress_enter}, {enter_sent}, {reason}: {actual}"


def check_paste_target_matching():
    window_target = (101, 1001, 501)
    exact_target = (*window_target, 501, 42, 7, 11)
    assert app.paste_target_identities_match(exact_target, exact_target)
    assert app.paste_target_identities_match(window_target, exact_target)
    assert app.paste_target_identities_match(exact_target, window_target)
    assert not app.paste_target_identities_match(exact_target, (*window_target, 501, 42, 7, 12))
    assert not app.paste_target_identities_match(window_target, (102, 1001, 501))
    assert not app.paste_target_identities_match(window_target, (101, 1002, 501))
    assert not app.paste_target_identities_match(window_target, (101, 1001, 502))
    assert not app.paste_target_identities_match(None, window_target)


class FakeClipboard:
    def __init__(self, value):
        self.value = value

    def paste(self):
        return self.value

    def copy(self, value):
        self.value = value


class DelayedClipboard:
    def __init__(self, value, delay_reads=2):
        self.value = value
        self.pending = None
        self.delay_reads = delay_reads
        self.remaining_reads = 0

    def paste(self):
        if self.pending is not None:
            if self.remaining_reads <= 0:
                self.value = self.pending
                self.pending = None
            else:
                self.remaining_reads -= 1
        return self.value

    def copy(self, value):
        self.pending = value
        self.remaining_reads = self.delay_reads


class FakeUser32:
    def IsClipboardFormatAvailable(self, _format):
        return 1


class TestEngine(app.DictationEngine):
    def __init__(
        self,
        cfg,
        send_ok=True,
        enter_ok=True,
        focus_callback=None,
        target_identity_callback=None,
    ):
        super().__init__(
            cfg,
            lambda _status: None,
            lambda *_args: None,
            focus_callback=focus_callback,
            target_identity_callback=target_identity_callback,
        )
        self.send_ok = send_ok
        self.enter_ok = enter_ok
        self.enter_count = 0

    def send_ctrl_v(self):
        return self.send_ok

    def send_enter(self):
        self.enter_count += 1
        return self.enter_ok


class BrokenKeyboard:
    def press(self, _key):
        raise RuntimeError("keyboard unavailable")

    def release(self, _key):
        return None


class CapturingTranscriptionEngine(app.DictationEngine):
    def __init__(self, cfg):
        super().__init__(cfg, lambda _status: None, lambda *_args: None)
        self.job_ready = threading.Event()
        self.release_job = threading.Event()
        self.captured_job = None

    def _transcribe_recording(self, job):
        self.captured_job = job
        self.job_ready.set()
        try:
            self.release_job.wait(timeout=3)
        finally:
            self._finish_transcription_worker()


def check_recording_job_is_atomic():
    cfg = app.default_config()
    engine = CapturingTranscriptionEngine(cfg)
    old_asr = object()
    old_block = app.np.ones((1600, 1), dtype=app.np.float32)
    engine.loaded = True
    engine.asr = old_asr
    engine.sample_rate = 16000
    engine.recording = True
    engine.audio_blocks = [old_block]
    engine.audio_callback_count = 1
    engine.audio_callback_statuses = ["old-status"]
    engine.recording_context = "old context"

    assert engine.stop_recording(suppress_enter_after_paste=True) is True
    assert engine.transcribing is True
    assert engine.recording is False
    assert engine.audio_blocks == []
    assert not engine.transcription_done.is_set()
    assert engine.job_ready.wait(timeout=2)

    job = engine.captured_job
    assert job is not None
    assert len(job.blocks) == 1 and job.blocks[0] is old_block
    assert job.asr is old_asr
    assert job.context == "old context"
    assert job.audio_callback_statuses == ("old-status",)
    assert job.suppress_enter_after_paste is True

    engine.audio_blocks = [app.np.zeros((800, 1), dtype=app.np.float32)]
    engine.recording_context = "new context"
    engine.asr = object()
    engine.start_recording()
    assert engine.recording is False

    assert engine.request_shutdown() is True
    assert engine.closing is True
    worker = engine.transcription_thread
    engine.release_job.set()
    assert engine.transcription_done.wait(timeout=2)
    if worker is not None:
        worker.join(timeout=2)
    assert engine.is_idle()
    engine.start_recording()
    assert engine.recording is False


def wait_until(predicate, timeout=3.0):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def fake_hardware_info(_cfg):
    return {
        "available": True,
        "version": "test",
        "devices": ["CPU", "NPU"],
        "device_names": {"CPU": "test CPU", "NPU": "test NPU"},
        "selected_devices": [],
        "warnings": [],
        "error": None,
    }


class AsrGenerationEngine(app.DictationEngine):
    def __init__(self, cfg):
        super().__init__(cfg, lambda _status: None, lambda *_args: None)
        self.started = {}
        self.release = {}
        self.results = {}

    def _load_asr_profile(self, model_id, _device, status_callback=None, cfg=None):
        self.started.setdefault(model_id, threading.Event()).set()
        release = self.release.setdefault(model_id, threading.Event())
        if not release.wait(timeout=5):
            raise TimeoutError(f"ASR generation test timed out: {model_id}")
        result = object()
        self.results[model_id] = result
        return result

    def _warmup_models(self, _asr, _punct, _cfg, status_callback=None):
        return None

    def ensure_audio_stream(self):
        return True

    def load_punct_async(self, _cfg):
        return False


def check_stale_asr_load_is_discarded():
    original_probe = app.probe_openvino_hardware
    cfg = app.default_config()
    old_model = cfg["asr_model"]
    new_model = app.OPENVINO_ASR_MODEL
    engine = AsrGenerationEngine(cfg)
    app.probe_openvino_hardware = fake_hardware_info
    try:
        assert engine.load_async() is True
        assert engine.started.setdefault(old_model, threading.Event()).wait(timeout=2)

        new_cfg = dict(engine.cfg)
        new_cfg.update({"asr_model": new_model, "asr_device": "NPU"})
        engine.update_config(new_cfg)
        latest_cfg = dict(engine.cfg)
        latest_cfg["overlay_opacity"] = 0.42
        engine.update_config(latest_cfg)

        engine.release.setdefault(old_model, threading.Event()).set()
        assert engine.started.setdefault(new_model, threading.Event()).wait(timeout=2)
        assert engine.asr is None
        assert engine.loaded is False

        engine.release.setdefault(new_model, threading.Event()).set()
        assert wait_until(lambda: engine.loaded and engine._asr_loading_generation is None)
        assert engine.asr is engine.results[new_model]
        assert engine.asr is not engine.results[old_model]
        assert engine.cfg["asr_model"] == new_model
        assert engine.cfg["overlay_opacity"] == 0.42
    finally:
        engine.release.setdefault(old_model, threading.Event()).set()
        engine.release.setdefault(new_model, threading.Event()).set()
        wait_until(lambda: engine._asr_loading_generation is None)
        app.probe_openvino_hardware = original_probe


class FakePollRoot:
    def __init__(self):
        self.after_calls = []

    def after(self, delay, callback):
        self.after_calls.append((delay, callback))


def check_stale_asr_status_is_discarded():
    cfg = app.default_config()
    ui = object.__new__(app.VoiceDictationApp)
    ui.event_queue = queue.Queue()
    ui.root = FakePollRoot()
    statuses = []
    ui.update_status = statuses.append

    engine = app.DictationEngine(
        cfg,
        lambda _status: None,
        lambda *_args: None,
        asr_status_callback=ui.queue_asr_status,
    )
    ui.engine = engine

    stale_generation = engine._asr_generation
    assert engine._set_asr_status(stale_generation, "Loading ASR") is True
    with engine.lock:
        engine._asr_generation += 1
    ui.poll_events()
    assert statuses == []

    current_generation = engine._asr_generation
    assert engine._set_asr_status(current_generation, "Ready") is True
    ui.poll_events()
    assert statuses == ["Ready"]
    assert len(ui.root.after_calls) == 2


class PunctGenerationEngine(app.DictationEngine):
    def __init__(self, cfg):
        super().__init__(cfg, lambda _status: None, lambda *_args: None)
        self.started = {}
        self.release = {}
        self.results = {}

    def _load_punct_profile(self, cfg, status_callback=None):
        device = cfg["punct_device"]
        self.started.setdefault(device, threading.Event()).set()
        release = self.release.setdefault(device, threading.Event())
        if not release.wait(timeout=5):
            raise TimeoutError(f"punct generation test timed out: {device}")
        result = object()
        self.results[device] = result
        return result


def check_stale_punct_load_is_discarded():
    cfg = app.default_config()
    old_device = cfg["punct_device"]
    new_device = "CPU" if old_device != "CPU" else "NPU"
    engine = PunctGenerationEngine(cfg)
    try:
        assert engine.load_punct_async(cfg) is True
        assert engine.started.setdefault(old_device, threading.Event()).wait(timeout=2)

        new_cfg = dict(engine.cfg)
        new_cfg["punct_device"] = new_device
        engine.update_config(new_cfg)
        engine.release.setdefault(old_device, threading.Event()).set()

        assert engine.started.setdefault(new_device, threading.Event()).wait(timeout=2)
        assert engine.punct is None
        engine.release.setdefault(new_device, threading.Event()).set()
        assert wait_until(lambda: engine._punct_loading_generation is None and engine.punct is not None)
        assert engine.punct is engine.results[new_device]
        assert engine.punct is not engine.results[old_device]
        assert engine._punct_loaded_generation == engine._punct_generation
    finally:
        engine.release.setdefault(old_device, threading.Event()).set()
        engine.release.setdefault(new_device, threading.Event()).set()
        wait_until(lambda: engine._punct_loading_generation is None)


class FakeAudioStream:
    def __init__(
        self,
        start_entered=None,
        start_release=None,
        fail_start=False,
        stop_entered=None,
        stop_release=None,
    ):
        self.start_entered = start_entered
        self.start_release = start_release
        self.fail_start = fail_start
        self.stop_entered = stop_entered
        self.stop_release = stop_release
        self.start_count = 0
        self.stop_count = 0
        self.close_count = 0

    def start(self):
        self.start_count += 1
        if self.start_entered is not None:
            self.start_entered.set()
        if self.start_release is not None and not self.start_release.wait(timeout=3):
            raise TimeoutError("audio start test timed out")
        if self.fail_start:
            raise RuntimeError("audio start failed")

    def stop(self):
        self.stop_count += 1
        if self.stop_entered is not None:
            self.stop_entered.set()
        if self.stop_release is not None and not self.stop_release.wait(timeout=3):
            raise TimeoutError("audio stop test timed out")

    def close(self):
        self.close_count += 1


class FakeAudioBackend:
    def __init__(self, fail_query=False):
        self.fail_query = fail_query
        self.stream_factory = FakeInputStreamFactory()
        self.InputStream = self.stream_factory

    def query_devices(self, device=None, kind=None):
        if self.fail_query:
            raise RuntimeError("device query failed")
        devices = [
            {
                "name": "Microphone Array",
                "hostapi": 0,
                "default_samplerate": 48000,
                "max_input_channels": 2,
            },
            {
                "name": "Output only",
                "hostapi": 0,
                "default_samplerate": 48000,
                "max_input_channels": 0,
            },
        ]
        if kind == "input":
            return devices[0]
        if device is not None:
            return devices[int(device)]
        return devices

    def query_hostapis(self, _index):
        return {"name": "Windows WASAPI"}


class FakeInputStreamFactory:
    def __init__(self, start_entered=None, start_release=None, fail_start=False):
        self.start_entered = start_entered
        self.start_release = start_release
        self.fail_start = fail_start
        self.instances = []

    def __call__(self, **_kwargs):
        stream = FakeAudioStream(self.start_entered, self.start_release, self.fail_start)
        self.instances.append(stream)
        return stream


def check_audio_stream_lifecycle_is_serialized():
    original_sd = app.sd
    cfg = app.default_config()
    cfg["sample_rate"] = 16000
    try:
        start_entered = threading.Event()
        start_release = threading.Event()
        factory = FakeInputStreamFactory(start_entered, start_release)
        backend = FakeAudioBackend()
        backend.InputStream = factory
        app.sd = backend
        engine = app.DictationEngine(cfg, lambda _status: None, lambda *_args: None)
        first_result = []
        first_worker = threading.Thread(target=lambda: first_result.append(engine.ensure_audio_stream()))
        first_worker.start()
        assert start_entered.wait(timeout=2)
        assert engine.ensure_audio_stream() is False
        assert len(factory.instances) == 1
        start_release.set()
        first_worker.join(timeout=2)
        assert not first_worker.is_alive()
        assert first_result == [True]
        stream = factory.instances[0]
        assert stream.start_count == 1
        engine.close_audio_stream()
        assert stream.stop_count == 1
        assert stream.close_count == 1

        start_entered = threading.Event()
        start_release = threading.Event()
        factory = FakeInputStreamFactory(start_entered, start_release)
        backend = FakeAudioBackend()
        backend.InputStream = factory
        app.sd = backend
        engine = app.DictationEngine(cfg, lambda _status: None, lambda *_args: None)
        ensure_result = []
        ensure_worker = threading.Thread(target=lambda: ensure_result.append(engine.ensure_audio_stream()))
        ensure_worker.start()
        assert start_entered.wait(timeout=2)
        assert engine.request_shutdown() is False
        close_done = threading.Event()

        def close_stream():
            engine.close_audio_stream(wait=False)
            close_done.set()

        close_worker = threading.Thread(target=close_stream)
        close_worker.start()
        assert close_done.wait(timeout=0.2)
        assert ensure_worker.is_alive()
        start_release.set()
        ensure_worker.join(timeout=2)
        close_worker.join(timeout=2)
        assert not ensure_worker.is_alive() and not close_worker.is_alive()
        assert ensure_result == [False]
        assert close_done.is_set()
        stream = factory.instances[0]
        assert stream.stop_count == 1 and stream.close_count == 1
        assert engine.stream is None

        statuses = []
        factory = FakeInputStreamFactory(fail_start=True)
        backend = FakeAudioBackend()
        backend.InputStream = factory
        app.sd = backend
        engine = app.DictationEngine(cfg, statuses.append, lambda *_args: None)
        assert engine.ensure_audio_stream() is False
        stream = factory.instances[0]
        assert stream.stop_count == 1 and stream.close_count == 1
        assert engine.stream is None and engine.stream_signature is None
        assert "Audio unavailable" in statuses
    finally:
        app.sd = original_sd


def check_ui_audio_operations_are_nonblocking():
    original_sd = app.sd
    release_events = []
    engines = []
    cfg = app.default_config()
    cfg["sample_rate"] = 16000
    try:
        start_entered = threading.Event()
        start_release = threading.Event()
        release_events.append(start_release)
        factory = FakeInputStreamFactory(start_entered, start_release)
        backend = FakeAudioBackend()
        backend.InputStream = factory
        app.sd = backend
        statuses = []
        engine = app.DictationEngine(cfg, statuses.append, lambda *_args: None)
        engines.append(engine)
        engine.loaded = True

        started_at = time.perf_counter()
        engine.start_recording()
        elapsed = time.perf_counter() - started_at
        assert elapsed < 0.5
        assert start_entered.wait(timeout=2)
        assert engine.recording is False
        assert "Starting audio" in statuses

        start_release.set()
        assert wait_until(lambda: engine.stream is not None and not engine._audio_open_task_pending)
        assert "Ready" in statuses
        engine.close_audio_stream()

        stop_entered = threading.Event()
        stop_release = threading.Event()
        start_entered = threading.Event()
        start_release = threading.Event()
        release_events.extend((stop_release, start_release))
        factory = FakeInputStreamFactory(start_entered, start_release)
        backend = FakeAudioBackend()
        backend.InputStream = factory
        app.sd = backend
        statuses = []
        engine = app.DictationEngine(cfg, statuses.append, lambda *_args: None)
        engines.append(engine)
        engine.loaded = True
        old_stream = FakeAudioStream(stop_entered=stop_entered, stop_release=stop_release)
        engine.stream = old_stream
        device_index = engine.cfg.get("input_device_index")
        engine.stream_signature = (device_index, 1, 16000)
        engine.sample_rate = 16000

        next_cfg = dict(engine.cfg)
        next_cfg["sample_rate"] = 22050
        started_at = time.perf_counter()
        engine.update_config(next_cfg)
        elapsed = time.perf_counter() - started_at
        assert elapsed < 0.5
        assert stop_entered.wait(timeout=2)
        assert start_entered.wait(timeout=2)
        assert old_stream.close_count == 0
        assert "Starting audio" in statuses

        stop_release.set()
        start_release.set()
        assert wait_until(lambda: old_stream.close_count == 1)
        assert wait_until(
            lambda: engine.stream is not None
            and engine.stream_signature == (device_index, 1, 22050)
            and not engine._audio_open_task_pending
        )
        assert "Ready" in statuses
        engine.close_audio_stream()

        start_entered = threading.Event()
        start_release = threading.Event()
        release_events.append(start_release)
        factory = FakeInputStreamFactory(start_entered, start_release)
        backend = FakeAudioBackend()
        backend.InputStream = factory
        app.sd = backend
        statuses = []
        engine = app.DictationEngine(cfg, statuses.append, lambda *_args: None)
        engines.append(engine)
        engine.loaded = True

        assert engine.ensure_audio_stream_async() is False
        assert start_entered.wait(timeout=2)
        next_cfg = dict(engine.cfg)
        next_cfg["sample_rate"] = 22050
        started_at = time.perf_counter()
        engine.update_config(next_cfg)
        assert time.perf_counter() - started_at < 0.5
        start_release.set()

        device_index = engine.cfg.get("input_device_index")
        assert wait_until(
            lambda: len(factory.instances) == 2
            and engine.stream is factory.instances[1]
            and engine.stream_signature == (device_index, 1, 22050)
            and not engine._audio_open_task_pending
            and engine._audio_opening_token is None
            and not engine._audio_open_retry_requested
        )
        assert factory.instances[0].stop_count == 1
        assert factory.instances[0].close_count == 1
        assert "Ready" in statuses
        engine.close_audio_stream()
    finally:
        for event in release_events:
            event.set()
        for engine in engines:
            engine.close_audio_stream(wait=False)
        app.sd = original_sd


def check_audio_discovery_is_recoverable():
    original_sd = app.sd
    try:
        app.sd = None
        assert app.input_devices() == []
        assert app.choose_default_device_index() is None
        cfg = app.default_config()
        assert cfg["input_device_index"] is None

        statuses = []
        engine = app.DictationEngine(cfg, statuses.append, lambda *_args: None)
        assert engine.ensure_audio_stream() is False
        assert statuses[-1] == "Audio unavailable"

        failing_backend = FakeAudioBackend(fail_query=True)
        assert app.input_devices(failing_backend) == []
        assert app.choose_default_device_index(failing_backend) is None

        working_backend = FakeAudioBackend()
        assert len(app.input_devices(working_backend)) == 1
        assert app.choose_default_device_index(working_backend) == 0
        app.sd = working_backend
        engine.cfg["sample_rate"] = 16000
        assert engine.ensure_audio_stream() is True
        engine.close_audio_stream()
    finally:
        app.sd = original_sd


class FakeCtypesFunction:
    def __init__(self, callback):
        self.callback = callback
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.callback(*args)


class FakeKernel32:
    def __init__(self, handle, error_ref=None, error=0):
        self.release_count = 0
        self.close_count = 0
        self.handle = handle
        self.error_ref = error_ref
        self.error = error
        self.CreateMutexW = FakeCtypesFunction(self._create)
        self.ReleaseMutex = FakeCtypesFunction(self._release)
        self.CloseHandle = FakeCtypesFunction(self._close)

    def _create(self, *_args):
        if self.error_ref is not None:
            self.error_ref[0] = self.error
        return self.handle

    def _release(self, _handle):
        self.release_count += 1
        return 1

    def _close(self, _handle):
        self.close_count += 1
        return 1


def check_single_instance_lock_states():
    original_system = app.platform.system
    original_windll = app.ctypes.WinDLL
    original_get_last_error = app.ctypes.get_last_error
    original_set_last_error = app.ctypes.set_last_error
    error_code = [0]
    app.platform.system = lambda: "Windows"
    app.ctypes.get_last_error = lambda: error_code[0]
    app.ctypes.set_last_error = lambda value: error_code.__setitem__(0, value)
    try:
        kernel = FakeKernel32(101, error_code, 0)
        app.ctypes.WinDLL = lambda *_args, **_kwargs: kernel
        lock = app.SingleInstanceLock("test-success")
        assert lock.acquire() is True and lock.acquired is True
        lock.release()
        assert kernel.release_count == 1 and kernel.close_count == 1

        kernel = FakeKernel32(202, error_code, app.SingleInstanceLock.ERROR_ALREADY_EXISTS)
        app.ctypes.WinDLL = lambda *_args, **_kwargs: kernel
        lock = app.SingleInstanceLock("test-existing")
        assert lock.acquire() is False and lock.acquired is False
        assert kernel.release_count == 0 and kernel.close_count == 1

        kernel = FakeKernel32(0, error_code, 5)
        app.ctypes.WinDLL = lambda *_args, **_kwargs: kernel
        lock = app.SingleInstanceLock("test-failure")
        try:
            lock.acquire()
        except app.SingleInstanceInitializationError as exc:
            assert exc.error_code == 5
        else:
            raise AssertionError("mutex initialization failure was accepted")
        assert lock.acquired is False
    finally:
        app.platform.system = original_system
        app.ctypes.WinDLL = original_windll
        app.ctypes.get_last_error = original_get_last_error
        app.ctypes.set_last_error = original_set_last_error


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

        app.pyperclip = DelayedClipboard("old", delay_reads=2)
        engine = TestEngine({"restore_clipboard_after_paste": False}, send_ok=True)
        assert engine.paste_text("new") is True
        assert app.pyperclip.value == "new"

        app.pyperclip = FakeClipboard("old")
        engine = TestEngine({"restore_clipboard_after_paste": True}, send_ok=False)
        engine.keyboard = BrokenKeyboard()
        assert engine.paste_text("new") is False
        assert app.pyperclip.value == "new"

        engine = TestEngine({"restore_clipboard_after_paste": True}, enter_ok=True)
        assert engine.press_enter_after_paste() is True
        assert engine.enter_count == 1

        engine = TestEngine({"restore_clipboard_after_paste": True}, enter_ok=False)
        engine.keyboard = BrokenKeyboard()
        assert engine.press_enter_after_paste() is False
        assert engine.enter_count == 1

        engine = TestEngine(
            {"restore_clipboard_after_paste": False},
            enter_ok=True,
            target_identity_callback=lambda: (101, 1001, 501, 501, 42, 7, 11),
        )
        assert engine.paste_text("new") is True
        assert engine.last_paste_target_identity == (101, 1001, 501, 501, 42, 7, 11)
        assert engine.press_enter_after_paste() is True
        assert engine.enter_count == 1

        current_target = [(101, 1001, 501, 501, 42, 7, 12)]
        engine = TestEngine(
            {"restore_clipboard_after_paste": False},
            enter_ok=True,
            target_identity_callback=lambda: current_target[0],
        )
        engine.last_paste_target_identity = (101, 1001, 501, 501, 42, 7, 11)
        assert engine.press_enter_after_paste() is False
        assert engine.enter_count == 0
        assert engine.last_enter_failure_reason == "target_changed"

        current_target = [(101, 1001, 501)]
        engine = TestEngine(
            {"restore_clipboard_after_paste": False},
            enter_ok=True,
            target_identity_callback=lambda: current_target[0],
        )
        assert engine.paste_text("new") is True
        current_target[0] = (101, 1001, 501, 501, 42, 7, 11)
        assert engine.press_enter_after_paste() is True
        assert engine.enter_count == 1

        engine = TestEngine(
            {"restore_clipboard_after_paste": False},
            enter_ok=True,
            focus_callback=lambda: False,
            target_identity_callback=lambda: (303, 3003, 503, 503, 42, 9),
        )
        assert engine.paste_text("new") is True
        assert engine.last_paste_target_identity is None
        assert engine.press_enter_after_paste() is False
        assert engine.enter_count == 0
        assert engine.last_enter_failure_reason == "target_unavailable"
    finally:
        app.pyperclip = original_clipboard
        app.ctypes.WinDLL = original_windll


def check_model_paths(runner):
    asr_dir = app.asr_model_dir()
    asr_openvino_dir = app.repo_root() / "models" / "asr" / "gigaam-v3-ctc-openvino-int8-calib96"
    punct_dir = app.default_punct_model_dir()
    manifest_path = model_setup.artifact_manifest_cache_path()
    if asr_dir.exists():
        runner.ok(f"ASR model directory exists: {asr_dir}")
    else:
        runner.warn(f"ASR model directory is missing: {asr_dir}")
    if asr_openvino_dir.exists():
        runner.ok(f"ASR OpenVINO artifact directory exists: {asr_openvino_dir}")
    else:
        runner.warn(f"ASR OpenVINO artifact directory is missing: {asr_openvino_dir}")
    if punct_dir.exists():
        runner.ok(f"Punctuation model directory exists: {punct_dir}")
    else:
        runner.warn(f"Punctuation model directory is missing: {punct_dir}")
    if manifest_path.exists():
        runner.ok(f"Model artifact manifest cache exists: {manifest_path}")
    else:
        runner.warn(f"Model artifact manifest cache is missing: {manifest_path}")


def check_model_artifact_helpers():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        payload = b"hello model"
        target = root / "models" / "test" / "artifact.bin"
        target.parent.mkdir(parents=True)
        target.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        artifact = {
            "profile_id": "unit-test-profile",
            "component": "unit",
            "repo_path": "unit/artifact.bin",
            "install_path": "models/test/artifact.bin",
            "size_bytes": len(payload),
            "sha256": digest,
        }
        manifest = {"artifacts": [artifact]}

        assert model_setup.safe_install_path("models/test/artifact.bin", root) == target.resolve()
        assert model_setup.artifact_ready(artifact, root)
        assert model_setup.profile_artifacts_ready(manifest, "unit-test-profile", "unit", root)

        target.write_bytes(b"bad")
        assert not model_setup.artifact_ready(artifact, root, verify_hash=False)
        assert not model_setup.artifact_ready(artifact, root, verify_hash=True)

        for unsafe in ("../outside.bin", "/absolute.bin", "models/../outside.bin"):
            try:
                model_setup.safe_install_path(unsafe, root)
            except ValueError:
                pass
            else:
                raise AssertionError(f"unsafe path accepted: {unsafe}")


class FakeDownloadResponse:
    def __init__(self, payload, content_length=None):
        self.payload = payload
        self.offset = 0
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def read(self, size):
        if self.offset >= len(self.payload):
            return b""
        chunk = self.payload[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


def check_direct_download_size_validation():
    original_urlopen = model_setup.urlopen
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "model.bin"
            target.write_bytes(b"existing")

            model_setup.urlopen = lambda *_args, **_kwargs: FakeDownloadResponse(b"data", 4)
            tmp = model_setup.download_url_to_file("https://example.invalid/model", target, label="test")
            assert tmp.read_bytes() == b"data"
            assert target.read_bytes() == b"existing"
            tmp.unlink()

            for declared_size in (5, 3):
                model_setup.urlopen = (
                    lambda *_args, _declared=declared_size, **_kwargs: FakeDownloadResponse(b"data", _declared)
                )
                try:
                    model_setup.download_url_to_file("https://example.invalid/model", target, label="test")
                except RuntimeError:
                    pass
                else:
                    raise AssertionError(f"Content-Length mismatch accepted: {declared_size}")
                assert not target.with_name(target.name + ".download").exists()
                assert target.read_bytes() == b"existing"

            model_setup.urlopen = lambda *_args, **_kwargs: FakeDownloadResponse(b"data", 99)
            tmp = model_setup.download_url_to_file(
                "https://example.invalid/model",
                target,
                expected_size=4,
                label="test",
            )
            assert tmp.read_bytes() == b"data"
            tmp.unlink()
    finally:
        model_setup.urlopen = original_urlopen


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
        "import re\n"
        "long_text = ' '.join(['сегодня мы проверяем длинную диктовку и сохранение всех слов'] * 40)\n"
        "result_long = restorer.restore(long_text)\n"
        "words = lambda text: re.findall(r'\\w+', text.casefold())\n"
        "assert words(result_long) == words(long_text), 'Long punctuation lost or duplicated words'\n"
        "assert '\\n' not in result_long and '\\r' not in result_long\n"
        "raw = 'продолжаем проверку после длинного контекста'\n"
        "assert words(restorer.restore_inserted(long_text, raw)) == words(raw)\n"
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


def check_punctuation_windows():
    import unittest
    from test_rupunct_windows import PunctuationWindowTests

    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(PunctuationWindowTests).run(result)
    assert result.wasSuccessful(), result.errors + result.failures


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run local smoke checks for NPU Dictate.")
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
    runner.check("config persistence is atomic and recoverable", check_config_persistence_is_recoverable)
    runner.check("install and user-data roots stay separate", check_app_and_data_roots_are_separate)
    runner.check("CPU-only fallback profile normalizes", check_cpu_fallback_profile)
    runner.check("hardware device filtering falls back to CPU", check_hardware_device_filtering)
    runner.check("model display labels map back to profile ids", check_model_display_labels)
    runner.check("download progress status includes size, speed, and ETA", check_download_status_format)
    runner.check("NPU ASR warmup is skipped to avoid startup hangs", check_npu_asr_warmup_is_skipped)
    runner.check("OpenVINO hardware probe runs", check_openvino_probe)
    runner.check("model artifact downloader helpers pass", check_model_artifact_helpers)
    runner.check("direct downloads validate Content-Length", check_direct_download_size_validation)
    runner.check("context-aware insertion spacing cases pass", check_insertion_spacing)
    runner.check("leading punctuation is removed before insertion", check_leading_punctuation_removal)
    runner.check("post-paste Enter statuses are explicit", check_post_paste_statuses)
    runner.check("post-paste target fallback remains window-guarded", check_paste_target_matching)
    runner.check("clipboard paste/restore behavior passes with mocks", check_clipboard_paste_behavior)
    runner.check("recording handoff is atomic and shutdown waits", check_recording_job_is_atomic)
    runner.check("stale ASR generations are discarded", check_stale_asr_load_is_discarded)
    runner.check("stale ASR status events are discarded", check_stale_asr_status_is_discarded)
    runner.check("stale punctuation generations are discarded", check_stale_punct_load_is_discarded)
    runner.check("audio stream lifecycle is serialized", check_audio_stream_lifecycle_is_serialized)
    runner.check("UI audio operations stay non-blocking", check_ui_audio_operations_are_nonblocking)
    runner.check("audio discovery failure is recoverable", check_audio_discovery_is_recoverable)
    runner.check("single-instance lock distinguishes all states", check_single_instance_lock_states)
    runner.check("punctuation windows preserve long text and context", check_punctuation_windows)
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
