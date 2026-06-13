import ctypes
import json
import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from ctypes import wintypes

import numpy as np
import onnx_asr
import pyperclip
import sounddevice as sd
from pynput import keyboard

from model_setup import ensure_asr_model, ensure_punct_model


APP_NAME = "Local Voice Dictation"
CONFIG_VERSION = 1


def repo_root():
    return Path(__file__).resolve().parents[1]


def config_path():
    return repo_root() / "voice_dictation_config.json"


def asr_model_dir():
    return repo_root() / "models" / "asr" / "gigaam-v3-ctc"


def default_punct_model_dir():
    return repo_root() / "models" / "openvino" / "RUPunct_big_fp16_static128"


def input_devices():
    devices = []
    for index, info in enumerate(sd.query_devices()):
        if int(info.get("max_input_channels", 0)) <= 0:
            continue
        hostapi = sd.query_hostapis(info["hostapi"])
        devices.append(
            {
                "index": index,
                "name": str(info["name"]),
                "hostapi": str(hostapi["name"]),
                "sample_rate": int(info["default_samplerate"]),
                "channels": int(info["max_input_channels"]),
            }
        )
    return devices


def choose_default_device_index():
    devices = input_devices()
    for device in devices:
        name = device["name"].lower()
        hostapi = device["hostapi"].lower()
        if "microphone array" in name and "wasapi" in hostapi:
            return device["index"]
    default = sd.query_devices(kind="input")
    for device in devices:
        if device["name"] == default["name"]:
            return device["index"]
    return devices[0]["index"] if devices else None


def default_config():
    return {
        "version": CONFIG_VERSION,
        "mode": "hold",
        "dictation_hotkey": "f8",
        "overlay_hotkey": "ctrl+alt+shift+d",
        "input_device_index": choose_default_device_index(),
        "sample_rate": 0,
        "channels": 1,
        "use_punctuation": True,
        "punct_device": "NPU",
        "auto_paste": True,
        "append_space": True,
        "overlay_visible": True,
        "overlay_x": None,
        "overlay_y": None,
    }


def load_config():
    cfg = default_config()
    path = config_path()
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
        cfg.update(loaded)
    return cfg


def save_config(cfg):
    path = config_path()
    with path.open("w", encoding="utf-8") as file:
        json.dump(cfg, file, ensure_ascii=False, indent=2)


def log_debug(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with (repo_root() / "voice_dictation.log").open("a", encoding="utf-8") as file:
            file.write(f"{timestamp} {message}\n")
    except OSError:
        pass


def key_to_token(key):
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.lower()
        return None

    name = getattr(key, "name", "").lower()
    if name.startswith("ctrl"):
        return "ctrl"
    if name.startswith("alt"):
        return "alt"
    if name.startswith("shift"):
        return "shift"
    if name.startswith("cmd"):
        return "win"
    return name


def parse_hotkey(value):
    aliases = {
        "control": "ctrl",
        "ctl": "ctrl",
        "option": "alt",
        "escape": "esc",
        "return": "enter",
        "windows": "win",
        "super": "win",
    }
    tokens = []
    for raw in value.lower().replace(" ", "").split("+"):
        if not raw:
            continue
        tokens.append(aliases.get(raw, raw))
    return frozenset(tokens)


def result_to_text(result):
    if isinstance(result, str):
        return result
    if hasattr(result, "text"):
        return result.text
    if isinstance(result, dict) and "text" in result:
        return str(result["text"])
    return str(result)


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class ForegroundWindowTracker:
    def __init__(self):
        self.enabled = os.name == "nt"
        self.last_target_hwnd = None
        self.last_focus_hwnd = None
        if not self.enabled:
            return

        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user32.GetAncestor.restype = wintypes.HWND
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.user32.IsWindow.argtypes = [wintypes.HWND]
        self.user32.IsWindow.restype = wintypes.BOOL
        self.user32.IsIconic.argtypes = [wintypes.HWND]
        self.user32.IsIconic.restype = wintypes.BOOL
        self.user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.ShowWindow.restype = wintypes.BOOL
        self.user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
        self.user32.AttachThreadInput.restype = wintypes.BOOL
        self.user32.BringWindowToTop.argtypes = [wintypes.HWND]
        self.user32.BringWindowToTop.restype = wintypes.BOOL
        self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user32.SetForegroundWindow.restype = wintypes.BOOL
        self.user32.SetFocus.argtypes = [wintypes.HWND]
        self.user32.SetFocus.restype = wintypes.HWND
        self.kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        self.current_pid = os.getpid()
        self.GWL_EXSTYLE = -20
        self.GA_ROOT = 2
        self.SW_RESTORE = 9
        self.WS_EX_NOACTIVATE = 0x08000000
        self.WS_EX_TOOLWINDOW = 0x00000080
        self.SWP_NOSIZE = 0x0001
        self.SWP_NOMOVE = 0x0002
        self.SWP_NOZORDER = 0x0004
        self.SWP_FRAMECHANGED = 0x0020

        long_ptr = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
        self.get_window_long = getattr(self.user32, "GetWindowLongPtrW", self.user32.GetWindowLongW)
        self.get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
        self.get_window_long.restype = long_ptr
        self.set_window_long = getattr(self.user32, "SetWindowLongPtrW", self.user32.SetWindowLongW)
        self.set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, long_ptr]
        self.set_window_long.restype = long_ptr
        self.user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        self.user32.SetWindowPos.restype = wintypes.BOOL
        self.user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.c_void_p]
        self.user32.GetGUIThreadInfo.restype = wintypes.BOOL
        self.user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user32.GetClassNameW.restype = ctypes.c_int

    def foreground_hwnd(self):
        if not self.enabled:
            return None
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            return None
        return self.user32.GetAncestor(hwnd, self.GA_ROOT) or hwnd

    def hwnd_pid(self, hwnd):
        pid = ctypes.c_ulong()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def is_usable_target(self, hwnd):
        if not self.enabled or not hwnd:
            return False
        if not self.user32.IsWindow(hwnd):
            return False
        return self.hwnd_pid(hwnd) != self.current_pid

    def observe_foreground(self):
        hwnd = self.foreground_hwnd()
        if self.is_usable_target(hwnd):
            self.last_target_hwnd = hwnd
            focus_hwnd = self.focus_hwnd_for_window(hwnd)
            if focus_hwnd and self.user32.IsWindow(focus_hwnd):
                self.last_focus_hwnd = focus_hwnd

    def restore_last_target(self):
        current = self.foreground_hwnd()
        if self.is_usable_target(current):
            self.last_target_hwnd = current
            focus_hwnd = self.focus_hwnd_for_window(current)
            if focus_hwnd and self.user32.IsWindow(focus_hwnd):
                self.last_focus_hwnd = focus_hwnd
            log_debug(
                "win current "
                f"target={self.describe_hwnd(current)} "
                f"focus={self.describe_hwnd(focus_hwnd)}"
            )
            return True

        hwnd = self.last_target_hwnd
        if not self.is_usable_target(hwnd):
            return False
        target_pid = self.hwnd_pid(hwnd)
        focus_hwnd = self.last_focus_hwnd if self.is_usable_focus(self.last_focus_hwnd, target_pid) else hwnd

        if self.user32.IsIconic(hwnd):
            self.user32.ShowWindow(hwnd, self.SW_RESTORE)

        foreground = self.user32.GetForegroundWindow()
        foreground_thread = self.user32.GetWindowThreadProcessId(foreground, None)
        target_thread = self.user32.GetWindowThreadProcessId(hwnd, None)
        focus_thread = self.user32.GetWindowThreadProcessId(focus_hwnd, None)
        current_thread = self.kernel32.GetCurrentThreadId()

        attached_foreground = False
        attached_target = False
        attached_focus = False
        try:
            if foreground_thread and foreground_thread != current_thread:
                attached_foreground = bool(self.user32.AttachThreadInput(current_thread, foreground_thread, True))
            if target_thread and target_thread != current_thread:
                attached_target = bool(self.user32.AttachThreadInput(current_thread, target_thread, True))
            if focus_thread and focus_thread not in {current_thread, target_thread}:
                attached_focus = bool(self.user32.AttachThreadInput(current_thread, focus_thread, True))

            self.user32.BringWindowToTop(hwnd)
            self.user32.SetForegroundWindow(hwnd)
            self.user32.SetFocus(focus_hwnd)
            log_debug(
                "win focus "
                f"target={self.describe_hwnd(hwnd)} "
                f"focus={self.describe_hwnd(focus_hwnd)}"
            )
            return self.is_foreground_target(hwnd, target_pid)
        finally:
            if attached_focus:
                self.user32.AttachThreadInput(current_thread, focus_thread, False)
            if attached_target:
                self.user32.AttachThreadInput(current_thread, target_thread, False)
            if attached_foreground:
                self.user32.AttachThreadInput(current_thread, foreground_thread, False)

    def is_foreground_target(self, hwnd, target_pid):
        deadline = time.perf_counter() + 0.6
        while time.perf_counter() < deadline:
            foreground = self.foreground_hwnd()
            if foreground == hwnd:
                return True
            if self.is_usable_target(foreground) and self.hwnd_pid(foreground) == target_pid:
                return True
            time.sleep(0.03)
        return False

    def make_no_activate(self, hwnd):
        if not self.enabled or not hwnd:
            return
        hwnd = self.user32.GetAncestor(hwnd, self.GA_ROOT) or hwnd
        style = int(self.get_window_long(hwnd, self.GWL_EXSTYLE))
        style |= self.WS_EX_NOACTIVATE | self.WS_EX_TOOLWINDOW
        self.set_window_long(hwnd, self.GWL_EXSTYLE, style)
        flags = self.SWP_NOMOVE | self.SWP_NOSIZE | self.SWP_NOZORDER | self.SWP_FRAMECHANGED
        self.user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, flags)

    def focus_hwnd_for_window(self, hwnd):
        if not self.enabled or not hwnd:
            return None

        thread_id = self.user32.GetWindowThreadProcessId(hwnd, None)
        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(GUITHREADINFO)
        if not self.user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
            return None
        return info.hwndFocus or info.hwndCaret or info.hwndActive

    def is_usable_focus(self, hwnd, target_pid):
        if not hwnd or not self.user32.IsWindow(hwnd):
            return False
        pid = self.hwnd_pid(hwnd)
        return pid == target_pid and pid != self.current_pid

    def describe_hwnd(self, hwnd):
        if not hwnd:
            return "None"
        class_name = ctypes.create_unicode_buffer(256)
        self.user32.GetClassNameW(hwnd, class_name, len(class_name))
        return f"{int(hwnd)}:{class_name.value}"


class FocusedInputTracker:
    TEXT_CONTROL_TYPES = {"EditControl", "DocumentControl", "TextControl"}

    def __init__(self):
        self.last_input = None
        self.current_pid = os.getpid()
        try:
            import uiautomation as auto
        except ImportError:
            self.auto = None
        else:
            self.auto = auto

    def observe_focused_input(self):
        if self.auto is None:
            return

        try:
            control = self.auto.GetFocusedControl()
            control = self.find_text_control(control)
            if control and int(control.ProcessId) != self.current_pid:
                self.last_input = control
        except Exception as exc:
            log_debug(f"uia observe error={type(exc).__name__}")

    def find_text_control(self, control):
        for _ in range(6):
            if control is None:
                return None
            if getattr(control, "ControlTypeName", "") in self.TEXT_CONTROL_TYPES:
                return control
            try:
                control = control.GetParentControl()
            except Exception:
                return None
        return None

    def restore_last_input(self):
        if self.last_input is None:
            return False

        try:
            import comtypes

            comtypes.CoInitialize()
            if int(self.last_input.ProcessId) == self.current_pid:
                return False
            self.last_input.SetFocus()
            log_debug(
                "uia focus "
                f"type={getattr(self.last_input, 'ControlTypeName', '')} "
                f"name={getattr(self.last_input, 'Name', '')!r}"
            )
            return True
        except Exception as exc:
            log_debug(f"uia focus error={type(exc).__name__}")
            return False


class HotkeyManager:
    def __init__(self, cfg, dispatch):
        self.cfg = cfg
        self.dispatch = dispatch
        self.pressed = set()
        self.dictation_down = False
        self.overlay_down = False
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.daemon = True

    def start(self):
        self.listener.start()

    def stop(self):
        self.listener.stop()

    def update_config(self, cfg):
        self.cfg = cfg
        self.dictation_down = False
        self.overlay_down = False

    def hotkeys(self):
        return parse_hotkey(self.cfg["dictation_hotkey"]), parse_hotkey(self.cfg["overlay_hotkey"])

    def on_press(self, key):
        token = key_to_token(key)
        if token:
            self.pressed.add(token)

        dictation_hotkey, overlay_hotkey = self.hotkeys()

        if overlay_hotkey and overlay_hotkey <= self.pressed and not self.overlay_down:
            self.overlay_down = True
            self.dispatch("toggle_overlay")

        if not dictation_hotkey or not dictation_hotkey <= self.pressed:
            return

        mode = self.cfg.get("mode", "hold")
        if mode == "toggle":
            if not self.dictation_down:
                self.dictation_down = True
                self.dispatch("toggle_recording")
        elif not self.dictation_down:
            self.dictation_down = True
            self.dispatch("start_recording")

    def on_release(self, key):
        token = key_to_token(key)
        if token:
            self.pressed.discard(token)

        dictation_hotkey, overlay_hotkey = self.hotkeys()

        if overlay_hotkey and not overlay_hotkey <= self.pressed:
            self.overlay_down = False

        if dictation_hotkey and not dictation_hotkey <= self.pressed:
            was_down = self.dictation_down
            self.dictation_down = False
            if was_down and self.cfg.get("mode", "hold") == "hold":
                self.dispatch("stop_recording")


class DictationEngine:
    def __init__(self, cfg, status_callback, text_callback, focus_callback=None):
        self.cfg = cfg
        self.status_callback = status_callback
        self.text_callback = text_callback
        self.focus_callback = focus_callback
        self.asr = None
        self.punct = None
        self.loaded = False
        self.loading = False
        self.recording = False
        self.transcribing = False
        self.stream = None
        self.sample_rate = None
        self.audio_blocks = []
        self.lock = threading.RLock()
        self.keyboard = keyboard.Controller()

    def update_config(self, cfg):
        with self.lock:
            self.cfg = cfg

    def set_status(self, status):
        self.status_callback(status)

    def load_async(self):
        if self.loading or self.loaded:
            return
        self.loading = True
        threading.Thread(target=self._load_models, daemon=True).start()

    def _load_models(self):
        try:
            ensure_asr_model(self.set_status)
            self.set_status("Loading ASR")
            asr = onnx_asr.load_model("gigaam-v3-ctc", asr_model_dir(), quantization="int8")

            punct = None
            if self.cfg.get("use_punctuation", True):
                from rupunct_restore import RUPunctRestorer

                ensure_punct_model(self.set_status)
                self.set_status("Loading punct")
                punct = RUPunctRestorer(
                    default_punct_model_dir(),
                    self.cfg.get("punct_device", "NPU"),
                    cache_dir=repo_root() / "models" / "openvino" / "cache",
                )

            with self.lock:
                self.asr = asr
                self.punct = punct
                self.loaded = True
                self.loading = False
            self.set_status("Ready")
        except Exception as exc:
            with self.lock:
                self.loading = False
            self.set_status(f"Load error: {type(exc).__name__}")

    def resolve_sample_rate(self):
        configured = int(self.cfg.get("sample_rate") or 0)
        if configured:
            return configured
        device_index = self.cfg.get("input_device_index")
        info = sd.query_devices(device_index, "input")
        return int(info["default_samplerate"])

    def start_recording(self):
        with self.lock:
            if self.recording or self.transcribing:
                return
            if not self.loaded:
                self.set_status("Still loading")
                self.load_async()
                return

            device_index = self.cfg.get("input_device_index")
            channels = int(self.cfg.get("channels") or 1)
            self.sample_rate = self.resolve_sample_rate()
            self.audio_blocks = []

            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=channels,
                dtype="float32",
                device=device_index,
                callback=self._audio_callback,
            )
            self.stream.start()
            self.recording = True
            self.set_status("Recording")

    def stop_recording(self):
        with self.lock:
            if not self.recording:
                return
            stream = self.stream
            self.stream = None
            self.recording = False

        if stream:
            stream.stop()
            stream.close()

        threading.Thread(target=self._transcribe_recording, daemon=True).start()

    def toggle_recording(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def cancel_recording(self):
        with self.lock:
            if not self.recording:
                return
            stream = self.stream
            self.stream = None
            self.recording = False
            self.audio_blocks = []

        if stream:
            stream.stop()
            stream.close()

        self.set_status("Ready" if self.loaded else "Starting")

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            self.set_status(str(status))
        self.audio_blocks.append(indata.copy())

    def _transcribe_recording(self):
        with self.lock:
            blocks = self.audio_blocks
            sample_rate = self.sample_rate
            self.transcribing = True

        try:
            if not blocks:
                self.set_status("No audio")
                return

            audio = np.concatenate(blocks, axis=0)
            if audio.ndim == 2 and audio.shape[1] > 1:
                audio = audio.mean(axis=1)
            else:
                audio = np.squeeze(audio)

            audio = np.ascontiguousarray(audio, dtype=np.float32)
            duration = len(audio) / sample_rate if sample_rate else 0.0
            if duration < 0.25:
                self.set_status("Too short")
                return

            self.set_status("Transcribing")
            start = time.perf_counter()
            raw_result = self.asr.recognize(audio, sample_rate=sample_rate)
            raw_text = result_to_text(raw_result).strip()
            asr_sec = time.perf_counter() - start

            final_text = raw_text
            punct_sec = 0.0
            if raw_text and self.cfg.get("use_punctuation", True):
                if self.punct is None:
                    from rupunct_restore import RUPunctRestorer

                    ensure_punct_model(self.set_status)
                    self.punct = RUPunctRestorer(
                        default_punct_model_dir(),
                        self.cfg.get("punct_device", "NPU"),
                        cache_dir=repo_root() / "models" / "openvino" / "cache",
                    )
                start = time.perf_counter()
                final_text = self.punct.restore(raw_text)
                punct_sec = time.perf_counter() - start

            if self.cfg.get("append_space", False) and final_text:
                final_text += " "

            if final_text:
                self.text_callback(raw_text, final_text, duration, asr_sec, punct_sec)
                if self.cfg.get("auto_paste", True):
                    if self.paste_text(final_text):
                        self.set_status("Pasted")
                    else:
                        self.set_status("Copied")
                else:
                    pyperclip.copy(final_text)
                    self.set_status("Copied")
            else:
                self.set_status("No speech")
        except Exception as exc:
            self.set_status(f"Error: {type(exc).__name__}")
        finally:
            with self.lock:
                self.transcribing = False

    def paste_text(self, text):
        pyperclip.copy(text)
        target_ready = None
        if self.focus_callback:
            target_ready = bool(self.focus_callback())
        time.sleep(0.12)

        sent = self.send_ctrl_v()
        log_debug(f"paste target_ready={target_ready} send_input={sent}")
        if sent:
            return True

        self.keyboard.press(keyboard.Key.ctrl)
        self.keyboard.press("v")
        self.keyboard.release("v")
        self.keyboard.release(keyboard.Key.ctrl)
        return True

    def send_ctrl_v(self):
        if os.name != "nt":
            return False

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
        INPUT_KEYBOARD = 1
        KEYEVENTF_KEYUP = 0x0002
        VK_CONTROL = 0x11
        VK_V = 0x56

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [
                ("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD),
            ]

        class INPUT_UNION(ctypes.Union):
            _fields_ = [
                ("mi", MOUSEINPUT),
                ("ki", KEYBDINPUT),
                ("hi", HARDWAREINPUT),
            ]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("union",)
            _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]

        def key_event(vk, flags=0):
            item = INPUT()
            item.type = INPUT_KEYBOARD
            item.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
            return item

        events = (INPUT * 4)(
            key_event(VK_CONTROL),
            key_event(VK_V),
            key_event(VK_V, KEYEVENTF_KEYUP),
            key_event(VK_CONTROL, KEYEVENTF_KEYUP),
        )

        user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        user32.SendInput.restype = wintypes.UINT
        ctypes.set_last_error(0)
        sent = user32.SendInput(len(events), events, ctypes.sizeof(INPUT))
        if sent != len(events):
            log_debug(f"sendinput failed sent={sent} error={ctypes.get_last_error()} input_size={ctypes.sizeof(INPUT)}")
        return sent == len(events)


class VoiceDictationApp:
    def __init__(self):
        self.cfg = load_config()
        self.event_queue = queue.Queue()
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_overlay)
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.root.configure(bg="#20242b")

        self.status_var = tk.StringVar(value="Starting")
        self.last_text_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value=self.cfg.get("mode", "hold"))
        self.progress_running = False
        self.drag_threshold = 8
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.overlay_start_x = 0
        self.overlay_start_y = 0
        self.dragging_overlay = False
        self.mouse_recording_active = False
        self.mouse_pressed_widget = None

        self.foreground_tracker = ForegroundWindowTracker()
        self.input_tracker = FocusedInputTracker()
        self.engine = DictationEngine(
            self.cfg,
            self.queue_status,
            self.queue_text,
            focus_callback=self.restore_target_window,
        )
        self.hotkeys = HotkeyManager(self.cfg, self.dispatch)

        self._build_overlay()
        self._position_overlay()
        self.foreground_tracker.make_no_activate(self.root.winfo_id())
        self._position_overlay()
        self._build_menu()

        if not self.cfg.get("overlay_visible", True):
            self.root.withdraw()

        self.root.after(100, self.poll_events)
        self.root.after(100, self.track_foreground)
        self.root.after(500, self.engine.load_async)
        self.hotkeys.start()

    def _build_overlay(self):
        self.frame = tk.Frame(self.root, bg="#20242b", padx=8, pady=7)
        self.frame.pack(fill="both", expand=True)

        self.button = tk.Button(
            self.frame,
            text="DICT",
            width=8,
            height=2,
            fg="white",
            bg="#2864d8",
            activeforeground="white",
            activebackground="#1f55bd",
            relief="flat",
        )
        self.button.pack(fill="x")

        self.status_label = tk.Label(
            self.frame,
            textvariable=self.status_var,
            fg="#d7deeb",
            bg="#20242b",
            font=("Segoe UI", 8),
        )
        self.status_label.pack(fill="x", pady=(5, 0))

        self.hotkey_label = tk.Label(
            self.frame,
            text=self.cfg.get("dictation_hotkey", "f8").upper(),
            fg="#8fa0bd",
            bg="#20242b",
            font=("Segoe UI", 7),
        )
        self.hotkey_label.pack(fill="x")

        self.progress = ttk.Progressbar(self.frame, mode="indeterminate", length=86)
        self.progress.pack(fill="x", pady=(5, 0))
        self.progress.pack_forget()

        for widget in (self.root, self.frame, self.button, self.status_label, self.hotkey_label):
            widget.bind("<Button-3>", self.show_menu)
            widget.bind("<ButtonPress-1>", self.on_overlay_press)
            widget.bind("<B1-Motion>", self.on_overlay_motion)
            widget.bind("<ButtonRelease-1>", self.on_overlay_release)

    def _position_overlay(self):
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth()
        height = self.root.winfo_reqheight()
        x = self.cfg.get("overlay_x")
        y = self.cfg.get("overlay_y")
        if x is None or y is None:
            left, top, right, bottom = self.virtual_screen_bounds()
            x = right - width - 32
            y = bottom - height - 80
        requested_x = x
        requested_y = y
        x, y = self.clamp_overlay_position(x, y, width, height)
        log_debug(
            "overlay position "
            f"requested=({requested_x},{requested_y}) "
            f"clamped=({x},{y}) "
            f"size=({width},{height}) "
            f"bounds={self.virtual_screen_bounds()}"
        )
        self.root.geometry(f"+{int(x)}+{int(y)}")
        if self.cfg.get("overlay_x") != x or self.cfg.get("overlay_y") != y:
            self.cfg["overlay_x"] = x
            self.cfg["overlay_y"] = y
            save_config(self.cfg)

    def virtual_screen_bounds(self):
        if os.name == "nt":
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            left = user32.GetSystemMetrics(76)
            top = user32.GetSystemMetrics(77)
            width = user32.GetSystemMetrics(78)
            height = user32.GetSystemMetrics(79)
            return left, top, left + width, top + height

        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def clamp_overlay_position(self, x, y, width=None, height=None):
        left, top, right, bottom = self.virtual_screen_bounds()
        width = int(width if width is not None else max(self.root.winfo_width(), self.root.winfo_reqwidth()))
        height = int(height if height is not None else max(self.root.winfo_height(), self.root.winfo_reqheight()))
        max_x = max(left, right - width)
        max_y = max(top, bottom - height)
        x = min(max(int(x), left), max_x)
        y = min(max(int(y), top), max_y)
        return x, y

    def _build_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Start/Stop", command=self.engine.toggle_recording)
        self.menu.add_command(label="Settings", command=self.open_settings)
        self.menu.add_command(label="Hide overlay", command=self.hide_overlay)
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.exit_app)

    def show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def dispatch(self, action):
        self.event_queue.put(("action", action))

    def queue_status(self, status):
        self.event_queue.put(("status", status))

    def queue_text(self, raw_text, final_text, duration, asr_sec, punct_sec):
        self.event_queue.put(("text", raw_text, final_text, duration, asr_sec, punct_sec))

    def poll_events(self):
        while True:
            try:
                item = self.event_queue.get_nowait()
            except queue.Empty:
                break

            if item[0] == "action":
                self.handle_action(item[1])
            elif item[0] == "status":
                self.update_status(item[1])
            elif item[0] == "text":
                _, raw_text, final_text, duration, asr_sec, punct_sec = item
                self.last_text_var.set(final_text)
                print(
                    f"audio={duration:.2f}s asr={asr_sec:.3f}s punct={punct_sec:.3f}s raw={raw_text} final={final_text}",
                    flush=True,
                )

        self.root.after(50, self.poll_events)

    def track_foreground(self):
        self.foreground_tracker.observe_foreground()
        self.input_tracker.observe_focused_input()
        self.root.after(100, self.track_foreground)

    def restore_target_window(self):
        window_restored = self.foreground_tracker.restore_last_target()
        if window_restored:
            log_debug("restore input=skipped-current-window window=True")
            return True

        input_restored = self.input_tracker.restore_last_input()
        if input_restored:
            self.foreground_tracker.observe_foreground()
            log_debug("restore input=True window=after-input")
            return True

        window_restored = self.foreground_tracker.restore_last_target()
        log_debug(f"restore input={input_restored} window={window_restored}")
        return window_restored

    def handle_action(self, action):
        if action == "toggle_overlay":
            self.toggle_overlay()
        elif action == "start_recording":
            self.engine.start_recording()
        elif action == "stop_recording":
            self.engine.stop_recording()
        elif action == "toggle_recording":
            self.engine.toggle_recording()

    def update_status(self, status):
        self.status_var.set(status)
        busy = (
            status.startswith("Downloading")
            or status.startswith("Converting")
            or status.startswith("Loading")
            or status in {"Still loading", "Transcribing"}
        )
        if busy and not self.progress_running:
            self.progress.pack(fill="x", pady=(5, 0))
            self.progress.start(12)
            self.progress_running = True
        elif not busy and self.progress_running:
            self.progress.stop()
            self.progress.pack_forget()
            self.progress_running = False

        if status == "Recording":
            self.button.configure(text="REC", bg="#b83030", activebackground="#982727")
        elif status in {"Transcribing", "Loading ASR", "Loading punct", "Still loading"}:
            self.button.configure(text="BUSY", bg="#81612b", activebackground="#6d5124")
        else:
            self.button.configure(text="DICT", bg="#2864d8", activebackground="#1f55bd")

    def on_overlay_press(self, event):
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        self.overlay_start_x = self.root.winfo_x()
        self.overlay_start_y = self.root.winfo_y()
        self.dragging_overlay = False
        self.mouse_pressed_widget = event.widget
        self.mouse_recording_active = False

        if event.widget == self.button and self.cfg.get("mode", "hold") == "hold":
            self.engine.start_recording()
            self.mouse_recording_active = True

    def on_overlay_motion(self, event):
        dx = event.x_root - self.drag_start_x
        dy = event.y_root - self.drag_start_y

        if not self.dragging_overlay and (dx * dx + dy * dy) < self.drag_threshold * self.drag_threshold:
            return

        if not self.dragging_overlay:
            self.dragging_overlay = True
            if self.mouse_recording_active:
                self.engine.cancel_recording()
                self.mouse_recording_active = False

        self.move_overlay(self.overlay_start_x + dx, self.overlay_start_y + dy)

    def on_overlay_release(self, event):
        if self.dragging_overlay:
            self.persist_overlay_position()
        elif self.mouse_pressed_widget == self.button:
            mode = self.cfg.get("mode", "hold")
            if mode == "hold" and self.mouse_recording_active:
                self.engine.stop_recording()
            elif mode == "toggle":
                self.engine.toggle_recording()

        self.dragging_overlay = False
        self.mouse_recording_active = False
        self.mouse_pressed_widget = None

    def move_overlay(self, x, y):
        x, y = self.clamp_overlay_position(x, y)
        self.root.geometry(f"+{x}+{y}")
        self.cfg["overlay_x"] = x
        self.cfg["overlay_y"] = y

    def persist_overlay_position(self):
        self.cfg["overlay_x"] = int(self.root.winfo_x())
        self.cfg["overlay_y"] = int(self.root.winfo_y())
        save_config(self.cfg)

    def toggle_overlay(self):
        if self.root.state() == "withdrawn":
            self.cfg["overlay_visible"] = True
            self.root.deiconify()
            self.root.attributes("-topmost", True)
        else:
            self.hide_overlay()
        save_config(self.cfg)

    def hide_overlay(self):
        self.cfg["overlay_visible"] = False
        save_config(self.cfg)
        self.root.withdraw()

    def open_settings(self):
        if hasattr(self, "settings_window") and self.settings_window.winfo_exists():
            self.settings_window.focus()
            return

        win = tk.Toplevel(self.root)
        self.settings_window = win
        win.title(APP_NAME + " Settings")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.configure(padx=12, pady=12)

        mode = tk.StringVar(value=self.cfg.get("mode", "hold"))
        dict_hotkey = tk.StringVar(value=self.cfg.get("dictation_hotkey", "f8"))
        overlay_hotkey = tk.StringVar(value=self.cfg.get("overlay_hotkey", "ctrl+alt+shift+d"))
        sample_rate = tk.StringVar(value=str(self.cfg.get("sample_rate", 0)))
        use_punctuation = tk.BooleanVar(value=bool(self.cfg.get("use_punctuation", True)))
        auto_paste = tk.BooleanVar(value=bool(self.cfg.get("auto_paste", True)))
        append_space = tk.BooleanVar(value=bool(self.cfg.get("append_space", False)))

        devices = input_devices()
        device_labels = [
            f"{d['index']}: {d['name']} [{d['hostapi']}, {d['sample_rate']} Hz]" for d in devices
        ]
        current_device = self.cfg.get("input_device_index")
        selected_device = tk.StringVar(value="")
        for label in device_labels:
            if label.startswith(f"{current_device}:"):
                selected_device.set(label)
                break
        if not selected_device.get() and device_labels:
            selected_device.set(device_labels[0])

        row = 0
        ttk.Label(win, text="Mode").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(win, textvariable=mode, values=["hold", "toggle"], state="readonly", width=24).grid(
            row=row, column=1, sticky="ew", pady=4
        )

        row += 1
        ttk.Label(win, text="Dictation hotkey").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(win, textvariable=dict_hotkey, width=28).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(win, text="Overlay hotkey").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(win, textvariable=overlay_hotkey, width=28).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(win, text="Input device").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(win, textvariable=selected_device, values=device_labels, state="readonly", width=56).grid(
            row=row, column=1, sticky="ew", pady=4
        )

        row += 1
        ttk.Label(win, text="Sample rate").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(win, textvariable=sample_rate, width=28).grid(row=row, column=1, sticky="w", pady=4)

        row += 1
        ttk.Checkbutton(win, text="Use punctuation", variable=use_punctuation).grid(
            row=row, column=1, sticky="w", pady=4
        )

        row += 1
        ttk.Checkbutton(win, text="Paste into active field", variable=auto_paste).grid(
            row=row, column=1, sticky="w", pady=4
        )

        row += 1
        ttk.Checkbutton(win, text="Append trailing space", variable=append_space).grid(
            row=row, column=1, sticky="w", pady=4
        )

        row += 1
        ttk.Label(win, textvariable=self.last_text_var, wraplength=420, foreground="#555").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(8, 4)
        )

        row += 1
        buttons = ttk.Frame(win)
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Hide overlay", command=self.hide_overlay).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save", command=lambda: self.save_settings(win, {
            "mode": mode.get(),
            "dictation_hotkey": dict_hotkey.get(),
            "overlay_hotkey": overlay_hotkey.get(),
            "input_device_index": int(selected_device.get().split(":", 1)[0]) if selected_device.get() else None,
            "sample_rate": int(sample_rate.get() or 0),
            "use_punctuation": bool(use_punctuation.get()),
            "auto_paste": bool(auto_paste.get()),
            "append_space": bool(append_space.get()),
        })).pack(side="left")

    def save_settings(self, win, values):
        values["dictation_hotkey"] = values["dictation_hotkey"].lower().strip()
        values["overlay_hotkey"] = values["overlay_hotkey"].lower().strip()
        if not parse_hotkey(values["dictation_hotkey"]):
            self.update_status("Bad hotkey")
            return
        if not parse_hotkey(values["overlay_hotkey"]):
            self.update_status("Bad overlay key")
            return

        self.cfg.update(values)
        save_config(self.cfg)
        self.hotkeys.update_config(self.cfg)
        self.engine.update_config(self.cfg)
        self.hotkey_label.configure(text=self.cfg["dictation_hotkey"].upper())
        self.update_status("Settings saved")
        win.destroy()

    def exit_app(self):
        save_config(self.cfg)
        self.hotkeys.stop()
        if self.engine.recording:
            self.engine.stop_recording()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    app = VoiceDictationApp()
    app.run()


if __name__ == "__main__":
    main()
