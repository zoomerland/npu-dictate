"""Hermetic startup preparation tests: fakes only, no devices or model files."""
import io
import queue
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import voice_dictation_app as app
import gigaam_openvino_asr as gigaam
import rupunct_restore as rupunct
from test_dictation_safety import FakeKeyboard, SafetyTests
from test_rupunct_windows import FakeTokenizer, FakeCompiled as PunctCompiled


REAL_PUNCT_LOAD = app.DictationEngine._load_punct_profile


class Compiled:
    def __init__(self, cached=None, failure=None):
        self.cached, self.failure, self.calls = cached, failure, []

    def get_property(self, name):
        assert name == "LOADED_FROM_CACHE"
        if isinstance(self.cached, Exception):
            raise self.cached
        return self.cached

    def __call__(self, inputs):
        self.calls.append(inputs)
        if self.failure:
            raise self.failure
        return {}


class Core:
    def __init__(self, compiled, on_compile=lambda: None):
        self.compiled, self.on_compile = compiled, on_compile
        self.reads, self.compiles, self.shapes = [], [], []

    def read_model(self, path):
        self.reads.append(path)
        return SimpleNamespace(reshape=self.shapes.append)

    def compile_model(self, *args):
        self.compiles.append(args)
        self.on_compile()
        return self.compiled

    def set_property(self, _properties):
        pass


class PreparationTests(unittest.TestCase):
    def setUp(self):
        for guard in (patch.object(app, "log_debug", lambda _s: None),
                      patch.object(app.keyboard, "Controller", FakeKeyboard),
                      patch.object(app, "log_openvino_hardware", lambda _h: None),
                      patch.object(app, "pending_model_downloads", lambda _cfg: []),
                      patch.object(app, "probe_openvino_hardware", lambda _cfg: self.hardware())):
            guard.start()
            self.addCleanup(guard.stop)

    @staticmethod
    def hardware():
        return dict(available=True, devices=["CPU", "NPU"], warnings=[], selected_devices={})

    def engine(self, **cfg_values):
        cfg = app.default_config()
        cfg.update(asr_model=app.OPENVINO_ASR_MODEL, asr_device="NPU", use_punctuation=False)
        cfg.update(cfg_values)
        statuses = []
        engine = app.DictationEngine(cfg, statuses.append, lambda *_a: None)
        engine.hardware_info = self.hardware()
        engine.statuses = statuses
        engine.ensure_audio_stream = lambda: self.fake_audio(engine)
        engine.ensure_audio_stream_async = lambda: self.fail("Unexpected audio open")
        return engine

    @staticmethod
    def fake_audio(engine):
        engine.stream = object()
        return True

    def asr(self, cached=None, failure=None, statuses=None):
        asr = gigaam.GigaamOpenVinoCtcAsr.__new__(gigaam.GigaamOpenVinoCtcAsr)
        asr.compiled, asr.lock = {}, threading.RLock()
        asr.model_path, asr.device, asr.device_config = Path("fake.onnx"), "NPU", {}
        asr.bucket_frames = (400, 800, 1000, 1600, 3200)
        asr.status_callback = (statuses if statuses is not None else []).append
        asr.core = Core(Compiled(cached, failure))
        return asr

    def loaded_engine(self, **cfg):
        engine = self.engine(**cfg)
        engine.loaded, engine.asr, engine.stream = True, object(), object()
        engine._asr_loaded_generation = engine._asr_generation
        return engine

    def ui(self, engine):
        ui = app.VoiceDictationApp.__new__(app.VoiceDictationApp)
        ui.cfg, ui.engine, ui.event_queue = dict(engine.cfg), engine, queue.Queue()
        ui.root = SimpleNamespace(after=lambda *_a: None)
        ui.displayed = []
        ui.update_status = ui.displayed.append
        engine.asr_status_callback = ui.queue_asr_status
        engine.punct_status_callback = ui.queue_punct_status
        return ui

    def test_actual_cache_classification_and_synthetic_inference(self):
        for cached, phase in ((True, "ASR cache loaded"), (False, "ASR compiled without cache"),
                              (RuntimeError("unsupported"), "ASR cache unknown"),
                              (None, "ASR cache unknown"), ("YES", "ASR cache unknown")):
            with self.subTest(cached=cached):
                statuses = []
                asr = self.asr(cached, statuses=statuses)
                self.assertEqual(asr.warmup([800]), [800])
                self.assertEqual(statuses, [f"Reading ASR model: 800 frames",
                    "Compiling ASR: 800 frames", f"{phase}: 800 frames", "Warming ASR: 800 frames"])
                self.assertEqual(len(asr.core.compiles), 1)
                inputs = asr.core.compiled.calls[0]
                self.assertEqual(inputs["features"].shape, (1, 64, 800))
                self.assertEqual(inputs["feature_lengths"].tolist(), [800])

    def test_in_memory_reuse_still_performs_warmup(self):
        statuses = []
        asr = self.asr(False, statuses=statuses)
        asr.warmup([400])
        statuses.clear()
        asr.warmup([400])
        self.assertEqual(statuses, ["ASR already in memory: 400 frames", "Warming ASR: 400 frames"])
        self.assertEqual(len(asr.core.compiles), 1)
        self.assertEqual(len(asr.core.compiled.calls), 2)

    def test_only_live_chunk_or_vad_bucket_is_prepared(self):
        for chunked, vad in ((True, False), (False, True), (True, True)):
            engine = self.engine(asr_chunked=chunked, asr_vad_segments=vad, asr_chunk_bucket=800)
            asr = self.asr()
            engine._warmup_models(asr, None, engine.cfg)
            self.assertEqual(list(asr.compiled), [800])

    def test_disabled_warmup_does_not_compile_or_infer(self):
        engine = self.loaded_engine(warmup_models=False)
        asr = self.asr()
        punct = SimpleNamespace(warmup=lambda: self.fail("Disabled punctuation warmup"))
        engine._warmup_models(asr, punct, engine.cfg)
        self.assertEqual(asr.core.reads, [])
        self.assertEqual(engine.readiness_status(), "Ready - warmup deferred")

    def test_cpu_default_without_warmup_uses_synthetic_recognition_before_ready(self):
        for enabled, fail in ((True, False), (False, False), (True, True)):
            with self.subTest(warmup_enabled=enabled, recognition_failure=fail):
                engine = self.engine(asr_model=app.DEFAULT_ASR_MODEL, asr_device="CPU",
                                     warmup_models=enabled)
                calls, events, errors = [], [], []
                engine.status_callback = lambda status: (engine.statuses.append(status), events.append(status))
                def recognize(audio, *, sample_rate):
                    calls.append((audio, sample_rate))
                    events.append("recognize")
                    self.assertFalse(engine.loaded)
                    self.assertIsNone(engine.asr)
                    if fail:
                        raise RuntimeError("Fake CPU inference failure")
                    return ""
                recognizer = SimpleNamespace(recognize=recognize)
                self.assertFalse(hasattr(recognizer, "warmup"))
                def load(model_id, device, _status, cfg):
                    self.assertEqual((model_id, device), (app.DEFAULT_ASR_MODEL, "CPU"))
                    self.assertEqual(cfg["warmup_models"], enabled)
                    return recognizer
                engine._load_asr_profile = load
                engine.ensure_audio_stream = lambda: (events.append("audio"), self.fake_audio(engine))[1]
                warmup = engine._warmup_models
                def observed_warmup(*args):
                    try:
                        return warmup(*args)
                    except app.ModelPreparationError as exc:
                        errors.append(exc)
                        raise
                engine._warmup_models = observed_warmup
                engine._asr_loading_generation, engine.loading = 0, True
                engine._load_models(0, dict(engine.cfg))
                self.assertEqual(len(calls), int(enabled))
                if calls:
                    audio, sample_rate = calls[0]
                    self.assertEqual((audio.shape, audio.dtype, sample_rate), ((16000,), np.dtype("float32"), 16000))
                    np.testing.assert_array_equal(audio, np.zeros(16000, dtype=np.float32))
                self.assertFalse(engine.loading)
                self.assertIsNone(engine._asr_loading_generation)
                if fail:
                    self.assertFalse(engine.loaded)
                    self.assertIsNone(engine.asr)
                    self.assertIsNone(engine._asr_loaded_generation)
                    self.assertEqual(len(errors), 1)
                    self.assertIsInstance(errors[0].__cause__, RuntimeError)
                    self.assertEqual(engine.statuses[-1], errors[0].status)
                    self.assertEqual(errors[0].status, "ASR preparation failed: RuntimeError")
                    self.assertNotIn("audio", events)
                    self.assertFalse(any(status.startswith("Ready") for status in engine.statuses))
                else:
                    self.assertEqual(errors, [])
                    self.assertTrue(engine.loaded)
                    self.assertIs(engine.asr, recognizer)
                    self.assertEqual(engine._asr_loaded_generation, 0)
                    expected = "Ready" if enabled else "Ready - warmup deferred"
                    self.assertEqual(engine.statuses[-1], expected)
                    self.assertEqual(engine.readiness_status(), expected)
                    self.assertLess(events.index("audio"), events.index(expected))
                    if enabled:
                        self.assertLess(events.index("recognize"), events.index("audio"))
                    else:
                        self.assertNotIn("Warming ASR", engine.statuses)

    def test_warmup_failure_is_not_swallowed(self):
        engine = self.engine()
        with self.assertRaises(app.ModelPreparationError) as caught:
            engine._warmup_models(self.asr(failure=RuntimeError("inference")), None, engine.cfg)
        self.assertEqual(caught.exception.status, "ASR preparation failed: RuntimeError")

    def test_asr_failed_compile_and_warmup_never_publish_ready(self):
        for compile_failure in (True, False):
            engine = self.engine()
            asr = self.asr(failure=None if compile_failure else RuntimeError("infer"))
            if compile_failure:
                asr.core.on_compile = lambda: (_ for _ in ()).throw(RuntimeError("compile"))
            engine._load_asr_profile = lambda *_a: asr
            engine._load_models(0, dict(engine.cfg))
            self.assertFalse(engine.loaded)
            self.assertIsNone(engine.asr)
            self.assertEqual(engine.statuses[-1], "ASR preparation failed: RuntimeError")

    def test_asr_compile_runs_in_background_without_engine_lock(self):
        engine = self.engine(asr_chunked=True, asr_vad_segments=False, asr_chunk_bucket=400)
        started, release = threading.Event(), threading.Event()
        def compile_wait():
            started.set()
            if not release.wait(3):
                raise AssertionError("Fake compile release timed out")
        asr = self.asr()
        asr.core.on_compile = compile_wait
        loads, workers = [], []
        def load(_m, _d, status, _cfg):
            loads.append((_m, _d))
            asr.status_callback = status
            return asr
        engine._load_asr_profile = load
        thread_class = threading.Thread
        def create_thread(*args, **kwargs):
            worker = thread_class(*args, **kwargs)
            workers.append(worker)
            return worker
        with patch.object(app.threading, "Thread", side_effect=create_thread):
            try:
                self.assertTrue(engine.load_async())
                self.assertTrue(started.wait(3))
                self.assertTrue(engine.lock.acquire(timeout=0.5))
                try:
                    self.assertTrue(engine.loading)
                    self.assertEqual(engine._asr_loading_generation, engine._asr_generation)
                finally:
                    engine.lock.release()
                engine.start_recording()
                self.assertFalse(engine.load_async())
                self.assertEqual(len(workers), 1)
                self.assertEqual(len(loads), 1)
                self.assertFalse(engine.recording)
                self.assertFalse(engine.loaded)
            finally:
                release.set()
                for worker in workers:
                    if worker.ident is not None:
                        worker.join(3)
                engine.request_shutdown()
        self.assertEqual(len(workers), 1)
        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(len(loads), 1)
        self.assertEqual(len(asr.core.compiles), 1)
        self.assertEqual(len(asr.core.compiled.calls), 1)
        self.assertFalse(engine.loading)
        self.assertIsNone(engine._asr_loading_generation)
        self.assertTrue(engine.loaded)
        self.assertEqual(engine.statuses[-1], "Ready")
        self.assertTrue(engine.closing)
        self.assertFalse(engine.load_async())

    def test_warmup_toggle_and_model_device_changes_invalidate_pending_load(self):
        for changes in (dict(warmup_models=False), dict(asr_device="CPU"),
                        dict(asr_model=app.DEFAULT_ASR_MODEL), dict(asr_chunk_bucket=400),
                        dict(asr_warmup_buckets=[400])):
            with self.subTest(changes=changes):
                engine = self.engine()
                started, release = threading.Event(), threading.Event()
                callbacks, restarts = [], []
                def load(_m, _d, status, _cfg):
                    callbacks.append(status)
                    started.set()
                    if not release.wait(3):
                        raise AssertionError("Fake load release timed out")
                    return self.asr()
                engine._load_asr_profile = load
                engine.load_async = lambda: restarts.append(True)
                worker = threading.Thread(target=engine._load_models, args=(0, dict(engine.cfg)))
                worker.start()
                try:
                    self.assertTrue(started.wait(3))
                    self.assertTrue(engine.update_config(dict(engine.cfg, **changes)))
                    self.assertEqual(engine._asr_generation, 1)
                    if "warmup_models" in changes:
                        self.assertEqual(engine._punct_generation, 1)
                    with self.assertRaises(app.PreparationSuperseded):
                        callbacks[0]("Compiling ASR: 800 frames")
                finally:
                    release.set()
                    worker.join(3)
                self.assertFalse(worker.is_alive())
                self.assertFalse(engine.loaded)
                self.assertIsNone(engine.asr)
                self.assertTrue(restarts)
                self.assertNotIn("Ready", engine.statuses)

    def test_punctuation_constructor_cache_stages_and_warmup(self):
        for cached, phase in ((True, "Punct cache loaded"), (False, "Punct compiled without cache"),
                              (RuntimeError("unsupported"), "Punct cache unknown")):
            statuses = []
            tokenizer = FakeTokenizer()
            compiled = PunctCompiled(tokenizer)
            compiled.get_property = Compiled(cached).get_property
            with patch.object(rupunct.ov, "Core", lambda: Core(compiled)), \
                 patch.object(rupunct.AutoTokenizer, "from_pretrained", lambda *_a, **_k: tokenizer), \
                 patch.object(Path, "open", lambda *_a, **_k: io.StringIO('{"id2label":{"0":"LOWER_O"}}')):
                punct = rupunct.RUPunctRestorer("fake-model", status_callback=statuses.append)
                punct.id2label = {0: "LOWER_O", 1: "UPPER_O", 2: "LOWER_PERIOD", 3: "LOWER_COMMA"}
                punct.warmup()
            self.assertEqual(statuses, ["Reading punct model", "Compiling punct", phase, "Warming punct"])
            self.assertEqual(len(compiled.calls), 1)

    def test_punctuation_profile_requires_warmup_unless_disabled(self):
        for enabled in (True, False):
            engine = self.engine(use_punctuation=True, warmup_models=enabled)
            calls = []
            class Restorer:
                def __init__(self, *_a, **kwargs):
                    calls.append("compile")
                    kwargs["status_callback"]("Compiling punct")
                def warmup(self):
                    calls.append("warmup")
            with patch.object(rupunct, "RUPunctRestorer", Restorer), \
                 patch.object(app, "ensure_punct_model", lambda *_a: None):
                REAL_PUNCT_LOAD(engine, engine.cfg, engine.statuses.append)
            self.assertEqual(calls, ["compile", "warmup"] if enabled else ["compile"])

    def test_punctuation_warmup_failure_remains_actionable_and_blocks_recording(self):
        engine = self.loaded_engine(use_punctuation=True)
        class Restorer:
            def __init__(self, *_a, **_k):
                pass
            def warmup(self):
                raise RuntimeError("infer")
        engine._load_punct_profile = lambda cfg, status: REAL_PUNCT_LOAD(engine, cfg, status)
        with patch.object(rupunct, "RUPunctRestorer", Restorer), \
             patch.object(app, "ensure_punct_model", lambda *_a: None):
            with self.assertRaises(app.ModelPreparationError):
                engine._get_punct(engine.cfg)
        self.assertIsNone(engine.punct)
        self.assertEqual(engine.readiness_status(), "Punct preparation failed: RuntimeError")
        engine.start_recording()
        self.assertFalse(engine.recording)

    def test_recording_blocked_before_and_during_configured_punctuation_preparation(self):
        for punct, loading in ((None, False), (None, True), (object(), True)):
            engine = self.loaded_engine(use_punctuation=True, warmup_models=True)
            engine.punct, engine.punct_loading = punct, loading
            engine.start_recording()
            self.assertFalse(engine.recording)
            self.assertEqual(engine.statuses[-1], "Loading punct")

    def presentation_ui(self, engine):
        ui = self.ui(engine)
        del ui.update_status
        ui.current_status = "Ready"
        ui.recording_started_at = ui.transcribing_started_at = None
        ui.set_display_status = lambda value: setattr(ui, "current_display_status", value)
        ui.schedule_status_tick = lambda: None
        ui.set_overlay_progress_running = lambda _running: None
        ui.apply_overlay_layout = lambda: None
        ui.draw_overlay = lambda: None
        engine.status_callback = ui.queue_status
        return ui

    def test_hotkey_start_and_toggle_preserve_current_pending_native_phase(self):
        for action in ("start_recording", "toggle_recording"):
            for phase in ("Compiling ASR: 800 frames", "Compiling punct"):
                with self.subTest(action=action, phase=phase):
                    engine = self.engine(use_punctuation=True)
                    if "ASR" in phase:
                        engine.loading, engine._asr_loading_generation = True, engine._asr_generation
                    else:
                        engine.loaded, engine.asr, engine.stream = True, object(), object()
                        engine.punct_loading = True
                        engine._punct_loading_generation = engine._punct_generation
                    ui = self.presentation_ui(engine)
                    ui.update_status(phase)
                    ui.handle_action(action)
                    ui.poll_events()
                    self.assertFalse(engine.recording)
                    self.assertEqual(ui.current_status, phase)
                    self.assertEqual(ui.model_load_status, phase)
                    self.assertEqual(ui.current_display_status, ui.localize_status(phase))
                    self.assertIsNone(ui.overlay_progress_percent)
                    failure = "ASR preparation failed: RuntimeError" if "ASR" in phase else "Punct preparation failed: RuntimeError"
                    ui.queue_status(failure)
                    ui.poll_events()
                    self.assertEqual(ui.current_status, failure)
                    ui.update_status(phase)
                    engine.loading = engine.punct_loading = False
                    placeholder = "Still loading" if "ASR" in phase else "Loading punct"
                    ui.update_status(placeholder)
                    self.assertEqual(ui.current_status, placeholder)

    def test_hotkeys_allow_disabled_warmup_punct_preload_and_do_not_intercept_stop(self):
        for action in ("start_recording", "toggle_recording"):
            engine = self.loaded_engine(use_punctuation=True, warmup_models=False, use_context=False)
            engine.punct_loading = True
            engine._punct_loading_generation = engine._punct_generation
            engine.context_before_cursor = lambda: ""
            ui = self.presentation_ui(engine)
            ui.update_status("Compiling punct")
            with patch.object(app, "system_cpu_times", lambda: None):
                ui.handle_action(action)
            ui.poll_events()
            self.assertTrue(engine.recording)
            self.assertEqual(ui.current_status, "Recording")
            stopped = []
            engine.stop_recording = lambda **kwargs: stopped.append(kwargs)
            for stop_action in ("stop_recording", "toggle_recording", "stop_without_enter"):
                ui.handle_action(stop_action)
            self.assertEqual(stopped, [{}, {"suppress_enter_after_paste": False},
                                       {"suppress_enter_after_paste": True}])

    def test_preparation_callbacks_detach_and_final_transcription_survives_shutdown(self):
        for enabled in (True, False):
            engine = self.engine(warmup_models=enabled, asr_vad_segments=False, asr_chunked=False,
                                 asr_retry_fragmented=False, auto_paste=False, append_space=False,
                                 use_context=False)
            preparation_statuses = []
            asr = self.asr(statuses=preparation_statuses)
            class Inference(Compiled):
                def output(self, name):
                    return name
                def __call__(self, inputs):
                    self.calls.append(inputs)
                    logits = np.zeros((1, 100, 2), dtype=np.float32)
                    logits[:, :, 0] = 1
                    return {"log_probs": logits}
            asr.core.compiled = Inference(False)
            asr.vocab, asr.blank_idx = {0: "final text", 1: ""}, 1
            asr._features = lambda *_a: (np.zeros((1, 64, 400), dtype=np.float32),
                                        np.array([400], dtype=np.int64))
            asr.last_chunks, asr.pad_mode = [], "zero"
            engine._warmup_models(asr, None, engine.cfg)
            self.assertIsNone(asr.status_callback)
            texts, copies = [], []
            engine.text_callback = lambda *args: texts.append(args)
            job = replace(SafetyTests.job(self, engine), asr=asr)
            count = len(preparation_statuses)
            engine.request_shutdown()
            with patch.object(app.pyperclip, "copy", copies.append):
                engine._transcribe_recording(job)
            self.assertEqual(texts[0][0], "final text")
            self.assertEqual(copies, ["final text"])
            self.assertEqual(len(preparation_statuses), count)
            self.assertEqual(engine.statuses[-1], "Copied")
            self.assertFalse(any(status.startswith("Error") for status in engine.statuses))

    def test_normal_compile_lookup_never_uses_retained_cooperative_callback(self):
        asr = self.asr()
        asr.status_callback = lambda _s: (_ for _ in ()).throw(app.PreparationSuperseded())
        compiled = asr._compile(400)
        self.assertIs(asr._compile(400), compiled)
        self.assertEqual(len(asr.core.compiles), 1)

    def test_pending_asr_shutdown_does_not_publish_success_or_error(self):
        for failure in (False, True):
            engine = self.engine()
            started, release = threading.Event(), threading.Event()
            def load(*_a):
                started.set()
                if not release.wait(3):
                    raise AssertionError("Fake close release timed out")
                if failure:
                    raise RuntimeError("old failure")
                return self.asr()
            engine._load_asr_profile = load
            restarts = []
            engine.load_async = lambda: restarts.append(True)
            worker = threading.Thread(target=engine._load_models, args=(0, dict(engine.cfg)))
            worker.start()
            try:
                self.assertTrue(started.wait(3))
                engine.request_shutdown()
                snapshot = list(engine.statuses)
            finally:
                release.set()
                worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertFalse(engine.loaded)
            self.assertEqual(engine.statuses, snapshot)
            self.assertEqual(restarts, [])

    def test_ui_consumer_discards_stale_phases_ready_errors_and_close(self):
        for close in (False, True):
            engine = self.loaded_engine(use_punctuation=True)
            ui = self.ui(engine)
            for status in ("Compiling ASR: 800 frames", "Ready", "ASR preparation failed: RuntimeError"):
                ui.queue_asr_status(0, status)
            for status in ("Compiling punct", "Ready", "Punct preparation failed: RuntimeError"):
                ui.queue_punct_status(0, status)
            if close:
                engine.request_shutdown()
            else:
                engine._asr_generation += 1
                engine._punct_generation += 1
            ui.poll_events()
            self.assertEqual(ui.displayed, [])
            self.assertFalse(engine._set_asr_status(0, "Ready"))
            self.assertFalse(engine._set_punct_status(0, engine._punct_signature, "Ready"))

    def test_queued_ready_is_reconciled_against_current_punctuation(self):
        engine = self.loaded_engine(use_punctuation=True)
        ui = self.ui(engine)
        ui.queue_asr_status(0, "Ready")
        ui.queue_punct_status(0, "Ready")
        ui.poll_events()
        self.assertEqual(ui.displayed, ["Loading punct", "Loading punct"])

    def test_stale_punctuation_failure_does_not_replace_current_state(self):
        engine = self.loaded_engine(use_punctuation=True)
        old_cfg, signature = dict(engine.cfg), engine._punct_signature
        sentinel = object()
        def stale_load(_cfg, _status):
            engine._punct_generation += 1
            engine.punct = sentinel
            raise RuntimeError("old failure")
        engine._load_punct_profile = stale_load
        engine._queue_current_punct_preload = lambda: None
        with self.assertRaises(RuntimeError):
            engine._load_punct_generation(0, signature, old_cfg)
        self.assertIs(engine.punct, sentinel)
        self.assertIsNone(engine.punct_error)

    def test_punctuation_policy_device_and_close_discard_pending_completion(self):
        for changes in (dict(warmup_models=False), dict(punct_device="CPU"), None):
            engine = self.loaded_engine(use_punctuation=True)
            signature, old_cfg = engine._punct_signature, dict(engine.cfg)
            restarts = []
            engine.load_async = lambda: restarts.append("asr")
            engine.load_punct_async = lambda _cfg: restarts.append("punct")
            engine._queue_current_punct_preload = lambda: restarts.append("latest")
            def load(_cfg, callback):
                if changes is None:
                    engine.request_shutdown()
                else:
                    engine.update_config(dict(engine.cfg, **changes))
                with self.assertRaises(app.PreparationSuperseded):
                    callback("Compiling punct")
                return object()
            engine._load_punct_profile = load
            engine._load_punct_generation(0, signature, old_cfg)
            self.assertIsNone(engine.punct)
            self.assertIsNone(engine.punct_error)
            self.assertNotIn("Ready", engine.statuses)

    def test_background_preparation_preserves_active_display_timer_button_and_tray(self):
        for active in ("Recording", "Transcribing"):
            engine = self.engine(warmup_models=False)
            engine.recording, engine.transcribing = active == "Recording", active == "Transcribing"
            ui = self.ui(engine)
            del ui.update_status
            ui.current_status = active
            ui.recording_started_at = 1.0 if engine.recording else None
            ui.transcribing_started_at = 1.0 if engine.transcribing else None
            ui.status_var = SimpleNamespace(set=lambda _value: None)
            tray = []
            ui.update_tray_status = lambda: tray.append(ui.current_status)
            ui.draw_overlay = lambda: None
            ui.schedule_status_tick = lambda: None
            ui.set_overlay_progress_running = lambda _running: None
            ui.apply_overlay_layout = lambda: None
            statuses = ["Ready - warmup deferred", "Ready", "Loading punct", "Still loading",
                        "Punct preparation failed: RuntimeError", "ASR preparation failed: RuntimeError"]
            statuses.extend(phase + (": 800 frames" if "ASR" in phase else "")
                            for phase in app.PREPARATION_PHASES)
            for status in statuses:
                ui.update_status(status)
                self.assertEqual(ui.model_load_status, status)
                self.assertEqual(ui.current_status, active)
                self.assertEqual(tray[-1], active)
                self.assertEqual(ui.overlay_button_text, "REC" if engine.recording else "TEXT")
                self.assertEqual(ui.recording_started_at if engine.recording else ui.transcribing_started_at, 1.0)

    def test_all_preparation_phases_localize_and_use_indeterminate_progress(self):
        engine = self.engine()
        ui = self.ui(engine)
        modes = []
        ui.settings_model_progress_bar = SimpleNamespace(stop=lambda: None, start=lambda _i: None,
                                                        configure=lambda **kw: modes.append(kw))
        for language in ("en", "ru"):
            ui.cfg["ui_language"] = language
            for phase in app.PREPARATION_PHASES:
                status = phase + (": 800 frames" if "ASR" in phase else "")
                localized = ui.localize_status(status)
                self.assertTrue(localized.startswith(app.TRANSLATIONS[language][phase]))
                if language == "ru":
                    self.assertNotIn(" frames", localized)
                self.assertIsNone(app.status_percent(status))
                ui.model_load_status = status
                ui.refresh_model_progress()
                self.assertEqual(modes[-1], dict(mode="indeterminate"))
            self.assertNotEqual(ui.localize_status("ASR preparation failed: RuntimeError"),
                                "ASR preparation failed: RuntimeError")
        ui.model_load_status = "Ready - warmup deferred"
        ui.refresh_model_progress()
        self.assertEqual(modes[-1], dict(mode="determinate", value=0))


if __name__ == "__main__":
    from headless_ux_checks import main
    raise SystemExit(main(test_cases=(PreparationTests,)))
