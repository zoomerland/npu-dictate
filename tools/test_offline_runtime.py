"""Process-only telemetry regressions; no GUI, audio, models or OS sandbox claim."""
import ast
import atexit
import builtins
import contextlib
import enum
import importlib
import importlib.machinery
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PACKAGE = "openvino_telemetry"
ENTRYPOINTS = ("voice_dictation_app", "gigaam_openvino_asr", "rupunct_restore")
NETWORK_EVENTS = frozenset({
    "socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg",
    "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr",
    "socket.getnameinfo",
})


def source_tree(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=path.name)


def isolated_helper(modules):
    """Execute the real helper with an isolated sys facade, never global modules."""
    code = compile(source_tree(TOOLS / "offline_runtime.py"), "offline_runtime.py", "exec")
    fake_sys = types.SimpleNamespace(modules=modules)
    imports = []

    def import_stdlib(name, *_args, **_kwargs):
        imports.append(name)
        if name != "sys":
            raise AssertionError("Unexpected helper import: " + name)
        return fake_sys

    namespace = {"__builtins__": dict(vars(builtins), __import__=import_stdlib)}
    exec(code, namespace)
    return namespace["disable_optional_telemetry"], imports


class PureTelemetryTests(unittest.TestCase):
    def test_root_block_and_idempotence_preserve_unrelated_modules(self):
        unrelated = object()
        modules = {"unrelated": unrelated, PACKAGE + "_unrelated": unrelated}
        disable, imports = isolated_helper(modules)
        disable()
        expected = dict(modules)
        disable()
        self.assertEqual(modules, expected)
        self.assertIn(PACKAGE, modules)
        self.assertIsNone(modules[PACKAGE])
        self.assertIs(modules["unrelated"], unrelated)
        self.assertEqual(imports, ["sys"])

    def test_blocked_root_prevents_root_and_child_imports(self):
        # Only this narrow import check touches global sys.modules; always restore it.
        with patch.dict(sys.modules):
            for name in tuple(sys.modules):
                if name == PACKAGE or name.startswith(PACKAGE + "."):
                    del sys.modules[name]
            disable, _ = isolated_helper(sys.modules)
            disable()
            for name in (PACKAGE, PACKAGE + ".backend", PACKAGE + ".backend.backend_ga4"):
                with self.subTest(module=name), self.assertRaises(ImportError):
                    importlib.import_module(name)

    def test_none_child_sentinels_are_not_preloaded_modules(self):
        modules = {PACKAGE: None, PACKAGE + ".backend": None}
        disable, _ = isolated_helper(modules)
        disable()
        self.assertEqual(modules, {PACKAGE: None, PACKAGE + ".backend": None})

    def test_late_root_and_children_fail_without_deleting_or_replacing(self):
        for name in (PACKAGE, PACKAGE + ".backend", PACKAGE + ".backend.backend_ga4"):
            for loaded in (types.ModuleType(name), False, 0):
                with self.subTest(module=name, loaded_type=type(loaded).__name__):
                    modules = {name: loaded, "unrelated": object()}
                    if name != PACKAGE:
                        modules[PACKAGE] = None
                    expected = dict(modules)
                    disable, _ = isolated_helper(modules)
                    with self.assertRaises(RuntimeError):
                        disable()
                    self.assertEqual(modules, expected)
                    self.assertIs(modules[name], loaded)

    def test_helper_has_no_environment_io_threads_or_network_side_effects(self):
        modules = {}
        disable, _ = isolated_helper(modules)
        environment = dict(os.environ)
        guards = (
            (builtins, "open"), (io, "open"), (os, "open"), (os, "mkdir"),
            (os, "putenv"), (os, "unsetenv"), (Path, "open"),
            (threading.Thread, "start"), (socket, "create_connection"),
        )
        with contextlib.ExitStack() as stack:
            mocks = [stack.enter_context(patch.object(owner, name,
                     side_effect=AssertionError("Forbidden helper side effect")))
                     for owner, name in guards]
            disable()
            disable()
            self.assertEqual(dict(os.environ), environment)
            for mocked in mocks:
                mocked.assert_not_called()


class BootstrapAstTests(unittest.TestCase):
    def assert_bootstrap_first(self, path):
        body = source_tree(path).body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            self.assertIsInstance(body[0].value.value, str)
            body = body[1:]
        while body and isinstance(body[0], ast.ImportFrom) and body[0].module == "__future__":
            body = body[1:]
        expected = ast.parse("from offline_runtime import disable_optional_telemetry\n"
                             "disable_optional_telemetry()\n").body
        self.assertEqual([ast.dump(node) for node in body[:2]],
                         [ast.dump(node) for node in expected], path.name)

    def test_each_entrypoint_bootstraps_before_runtime_imports(self):
        for name in ENTRYPOINTS:
            with self.subTest(entrypoint=name):
                self.assert_bootstrap_first(TOOLS / (name + ".py"))

    def test_runtime_hook_bootstraps_before_user_imports(self):
        self.assert_bootstrap_first(ROOT / "packaging/hooks/rthook_offline_runtime.py")

    def test_helper_imports_only_stdlib(self):
        imports = [node for node in ast.walk(source_tree(TOOLS / "offline_runtime.py"))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertTrue(imports)
        for node in imports:
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module]
            self.assertTrue(all(name.split(".")[0] in sys.stdlib_module_names for name in names))

    def test_spec_excludes_optional_dependency_and_collects_policy_and_hook(self):
        tree = source_tree(ROOT / "packaging/npu_dictate.spec")
        analyses = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name) and node.func.id == "Analysis"]
        self.assertEqual(len(analyses), 1)
        keywords = {item.arg: item.value for item in analyses[0].keywords}
        self.assertIn(PACKAGE, ast.literal_eval(keywords["excludes"]))
        self.assertIn("offline_runtime", ast.literal_eval(keywords["hiddenimports"]))
        self.assertNotIn(PACKAGE, ast.literal_eval(keywords["hiddenimports"]))
        hook = ast.parse('str(project_root / "packaging" / "hooks" / '
                         '"rthook_offline_runtime.py")', mode="eval").body
        self.assertIsInstance(keywords["runtime_hooks"], ast.List)
        self.assertIn(ast.dump(hook), [ast.dump(node) for node in keywords["runtime_hooks"].elts])


def network_audit(event, _args, record):
    if event in NETWORK_EVENTS:
        record(event)
        raise RuntimeError("Network denied by import regression")


def is_model_data(path):
    return path.resolve().is_relative_to(ROOT / "models")


class GuardTests(unittest.TestCase):
    def test_model_guard_allows_dependency_code_but_not_model_data(self):
        self.assertFalse(is_model_data(Path("site-packages/onnx_asr/models/gigaam.py")))
        self.assertFalse(is_model_data(Path("site-packages/transformers/models/__init__.pyc")))
        self.assertFalse(is_model_data(Path("site-packages/transformers/models/auto/config.json")))
        for name in ("model.onnx", "model.bin", "config.json", "model.xml"):
            with self.subTest(file=name):
                self.assertTrue(is_model_data(ROOT / "models" / name))

    def test_latch_survives_swallowed_background_network_exception(self):
        events = []

        def background():
            try:
                network_audit("socket.connect", (), events.append)
            except RuntimeError:
                pass

        worker = threading.Thread(target=background)
        worker.start()
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(events, ["socket.connect"])

    def test_dns_and_connections_denied_but_local_hostname_is_allowed(self):
        events = []
        network_audit("socket.gethostname", (), events.append)
        self.assertEqual(events, [])
        for event in NETWORK_EVENTS:
            with self.subTest(event=event), self.assertRaises(RuntimeError):
                network_audit(event, (), events.append)
        self.assertEqual(set(events), NETWORK_EVENTS)


def install_input_fakes(deny):
    for name, members in {
        "sounddevice": ("InputStream", "OutputStream", "query_devices", "rec", "play"),
        "soundfile": ("SoundFile", "read", "write"),
        "pyperclip": ("copy", "paste"),
        "pystray": ("Icon", "Menu", "MenuItem"),
    }.items():
        module = types.ModuleType(name)
        module.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
        for member in members:
            setattr(module, member, deny)
        sys.modules[name] = module
    keyboard = types.ModuleType("pynput.keyboard")
    keyboard.Key = enum.Enum("Key", "ctrl shift alt cmd enter esc space tab")
    keyboard.KeyCode = type("KeyCode", (), {"__init__": deny})
    keyboard.Controller = keyboard.Listener = deny
    pynput = types.ModuleType("pynput")
    pynput.__path__ = []
    pynput.keyboard = keyboard
    sys.modules.update({"pynput": pynput, "pynput.keyboard": keyboard})
    import tkinter
    import _tkinter
    tkinter.Tk = tkinter.Toplevel = tkinter.Tcl = _tkinter.create = deny


def run_probe(target, scratch):
    """Guards precede all third-party imports; records contain no URLs or input."""
    scratch = Path(scratch).resolve()
    report = {"target": target, "ok": False, "error_type": None}
    latch = scratch / "violations.jsonl"
    report_path = scratch / "report.json"
    original_open = builtins.open

    def record(label):
        with original_open(latch, "a", encoding="ascii") as handle:
            handle.write(json.dumps(label) + "\n")
            handle.flush()

    def deny(*_args, **_kwargs):
        record("UI/input")
        raise RuntimeError("UI/input forbidden")

    def audit(event, args):
        network_audit(event, args, record)
        if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.exec"}:
            record("child-process")
            raise RuntimeError("Child processes forbidden")
        if event == "open":
            path = args[0]
            if isinstance(path, (str, bytes, os.PathLike)):
                parts = Path(os.fsdecode(path)).parts
                if PACKAGE in (part.lower() for part in parts):
                    record("consent-file-access")
                    raise RuntimeError("Consent-file access forbidden")
                if is_model_data(Path(os.fsdecode(path))):
                    record("model-file-access")
                    raise RuntimeError("Model files forbidden")

    def finalize():
        report["violations"] = bool(latch.exists())
        with original_open(report_path, "w", encoding="ascii") as handle:
            json.dump(report, handle)

    # Registered first, so normal third-party atexit callbacks run before this receipt.
    atexit.register(finalize)
    sys.addaudithook(audit)
    try:
        install_input_fakes(deny)
        sys.path.insert(0, str(TOOLS))
        if target == "openvino":
            from offline_runtime import disable_optional_telemetry
            disable_optional_telemetry()
        else:
            importlib.import_module(target)
        import openvino as ov
        from openvino.tools.ovc import telemetry_utils, telemetry_stub
        assert telemetry_utils.tm is telemetry_stub
        assert sys.modules[PACKAGE] is None
        assert not any(name.startswith(PACKAGE + ".") and value is not None
                       for name, value in tuple(sys.modules.items()))
        assert callable(ov.Core)  # Do not create Core, compile or touch a model.
        assert ov.__file__ and telemetry_stub.__file__
        report.update(fallback=telemetry_utils.tm.__name__, core_callable=True,
                      openvino_version=ov.__version__)
        # Permit pending import-time Python callbacks to execute under the latch.
        time.sleep(0.5)
        active = [worker for worker in threading.enumerate()
                  if worker is not threading.current_thread()]
        deadline = time.monotonic() + 3
        for worker in active:
            worker.join(max(0, deadline - time.monotonic()))
        report["remaining_threads"] = sum(worker.is_alive() for worker in active)
        assert report["remaining_threads"] == 0
        report["ok"] = not latch.exists()
    except BaseException as exc:
        report["error_type"] = type(exc).__name__
    return 0 if report["ok"] else 1


class RealImportTests(unittest.TestCase):
    first_red = None

    def probe(self, target):
        if self.first_red is not None:
            self.skipTest("Stopped after first red import probe: " + self.first_red)
        self.addCleanup(self.stop_on_red)
        with tempfile.TemporaryDirectory(prefix="npu-offline-import-") as folder:
            scratch = Path(folder)
            environment = os.environ.copy()
            # Do not inherit a consent/CI opt-out that could conceal a regression.
            for name in tuple(environment):
                if name.upper().startswith(("OV_", "OPENVINO_")) or name.upper() in {
                    "CI", "CODEX_CI", "PYTHONPATH", "PYTHONHOME", "GITHUB_ACTIONS",
                    "JENKINS_URL", "TF_BUILD", "TEAMCITY_VERSION", "LOCAL_VOICE_DICTATION_APP_ROOT",
                }:
                    environment.pop(name)
            for name in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP",
                         "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "HF_HOME", "TORCH_HOME",
                         "LOCAL_VOICE_DICTATION_DATA_ROOT"):
                directory = scratch / name.lower()
                directory.mkdir()
                environment[name] = str(directory)
            environment["HOMEDRIVE"], environment["HOMEPATH"] = os.path.splitdrive(environment["USERPROFILE"])
            self.assertFalse(any(scratch.rglob(PACKAGE)))
            command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                       "--probe", target, str(scratch)]
            # Disk-backed capture and bounded readback, never dependency stdout in handoff.
            with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                try:
                    result = subprocess.run(command, cwd=scratch, env=environment,
                                            stdin=subprocess.DEVNULL, stdout=stdout,
                                            stderr=stderr, timeout=45, check=False)
                except subprocess.TimeoutExpired:
                    self.fail("Probe timeout; subprocess killed and waited by subprocess.run")
                stdout_size, stderr_size = stdout.tell(), stderr.tell()
            path = scratch / "report.json"
            self.assertTrue(path.is_file(), "No probe receipt; output byte counts="
                            + str((stdout_size, stderr_size)))
            self.assertLess(path.stat().st_size, 4096)
            report = json.loads(path.read_text(encoding="ascii"))
            latch = scratch / "violations.jsonl"
            violations = []
            if latch.exists():
                with latch.open(encoding="ascii") as handle:
                    violations = [json.loads(line) for line in handle.read(2048).splitlines()]
            self.assertFalse(violations, "Denied operations (first red): " + str(violations))
            self.assertEqual(result.returncode, 0, str(report))
            self.assertTrue(report["ok"], str(report))
            self.assertFalse(report["violations"])
            self.assertEqual(report["fallback"], "openvino.tools.ovc.telemetry_stub")
            self.assertTrue(report["core_callable"])
            self.assertEqual(report["remaining_threads"], 0)
            self.assertFalse(any(scratch.rglob(PACKAGE)), "Consent file created")

    def stop_on_red(self):
        # unittest continues discovery, but never launch another real probe after red.
        result = self._outcome.result
        if any(test is self for test, _ in result.failures + result.errors):
            type(self).first_red = self.id().rsplit(".", 1)[-1]

    def test_openvino_vendor_fallback_fresh_home(self):
        self.probe("openvino")

    def test_gigaam_wrapper_real_dependencies_fresh_home(self):
        self.probe("gigaam_openvino_asr")

    def test_rupunct_wrapper_real_dependencies_fresh_home(self):
        self.probe("rupunct_restore")

    def test_voice_app_import_real_backends_without_input_fresh_home(self):
        self.probe("voice_dictation_app")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--probe":
        sys.exit(run_probe(sys.argv[2], sys.argv[3]))
    unittest.main()
