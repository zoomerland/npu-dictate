import ctypes
import json
import os
import platform
import queue
import re
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from ctypes import wintypes

import numpy as np
import onnx_asr
import pyperclip
import sounddevice as sd
from pynput import keyboard

from model_setup import ensure_asr_model, ensure_punct_model

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None
    Image = None
    ImageDraw = None


APP_NAME = "Local Voice Dictation"
CONFIG_VERSION = 1
UI_LANGUAGE_NAMES = {
    "en": "English",
    "ru": "Русский",
}
UI_LANGUAGE_BY_NAME = {name: code for code, name in UI_LANGUAGE_NAMES.items()}
TRANSLATIONS = {
    "en": {
        "settings_title": "Settings",
        "status_prefix": "Status",
        "start_stop": "Start/Stop",
        "settings": "Settings",
        "show_overlay": "Show overlay",
        "hide_overlay": "Hide overlay",
        "copy_debug_info": "Copy debug info",
        "exit": "Exit",
        "quit": "Quit",
        "mode": "Mode",
        "mode_hold": "Hold to talk",
        "mode_toggle": "Toggle",
        "ui_language": "Interface language",
        "overlay_size": "Overlay size",
        "overlay_size_small": "Small",
        "overlay_size_medium": "Medium",
        "overlay_size_large": "Large",
        "overlay_details": "Overlay details",
        "overlay_details_button": "Button only",
        "overlay_details_status": "Button + status",
        "overlay_details_full": "Full",
        "overlay_opacity": "Overlay opacity",
        "dictation_hotkey": "Dictation hotkey",
        "overlay_hotkey": "Overlay hotkey",
        "input_device": "Input device",
        "sample_rate": "Sample rate",
        "use_punctuation": "Use punctuation",
        "paste_into_active_field": "Paste into active field",
        "use_context": "Use text before cursor",
        "append_trailing_space": "Append trailing space",
        "start_with_windows": "Start with Windows",
        "button_dict": "DICT",
        "button_record": "REC",
        "button_asr": "ASR",
        "button_punct": "PUNCT",
        "button_text": "TEXT",
        "button_busy": "BUSY",
        "button_ok": "OK",
        "button_copy": "COPY",
        "button_paste": "PASTE",
        "button_empty": "EMPTY",
        "button_error": "ERR",
        "assign": "Assign",
        "press_keys": "Press keys...",
        "apply": "Apply",
        "save": "Save",
        "cancel": "Cancel",
        "unsaved_settings": "Unsaved settings",
        "save_settings_before_closing": "Save settings before closing?",
        "load_error": "Load error",
        "error": "Error",
        "Loading models": "Loading models",
        "Downloading ASR": "Downloading ASR",
        "Loading ASR": "Loading ASR",
        "Downloading punct": "Downloading punct",
        "Converting punct": "Converting punct",
        "Loading punct": "Loading punct",
        "Ready": "Ready",
        "Starting": "Starting",
        "Still loading": "Still loading",
        "Recording": "Recording",
        "Transcribing": "Transcribing",
        "Pasted": "Pasted",
        "Copied": "Copied",
        "Copied - paste manually": "Copied - paste manually",
        "No audio": "No audio",
        "Too short": "Too short",
        "No speech": "No speech",
        "Debug copied": "Debug copied",
        "Hotkey captured": "Hotkey captured",
        "Hotkey capture canceled": "Hotkey capture canceled",
        "Press hotkey": "Press hotkey",
        "Finish hotkey capture": "Finish hotkey capture",
        "Bad sample rate": "Bad sample rate",
        "Bad hotkey": "Bad hotkey",
        "Bad overlay key": "Bad overlay key",
        "Hotkey conflict": "Hotkey conflict",
        "Startup error": "Startup error",
        "Settings saved": "Settings saved",
    },
    "ru": {
        "settings_title": "Настройки",
        "status_prefix": "Статус",
        "start_stop": "Старт/стоп",
        "settings": "Настройки",
        "show_overlay": "Показать кнопку",
        "hide_overlay": "Скрыть кнопку",
        "copy_debug_info": "Скопировать диагностику",
        "exit": "Выход",
        "quit": "Выйти",
        "mode": "Режим",
        "mode_hold": "Удерживать",
        "mode_toggle": "Нажать старт/стоп",
        "ui_language": "Язык интерфейса",
        "overlay_size": "Размер кнопки",
        "overlay_size_small": "Маленькая",
        "overlay_size_medium": "Средняя",
        "overlay_size_large": "Большая",
        "overlay_details": "Детализация кнопки",
        "overlay_details_button": "Только кнопка",
        "overlay_details_status": "Кнопка и статус",
        "overlay_details_full": "Полная",
        "overlay_opacity": "Прозрачность кнопки",
        "dictation_hotkey": "Горячая клавиша диктовки",
        "overlay_hotkey": "Горячая клавиша кнопки",
        "input_device": "Микрофон",
        "sample_rate": "Частота дискретизации",
        "use_punctuation": "Использовать пунктуацию",
        "paste_into_active_field": "Вставлять в активное поле",
        "use_context": "Учитывать текст перед курсором",
        "append_trailing_space": "Добавлять пробел в конце",
        "start_with_windows": "Запускать вместе с Windows",
        "button_dict": "ДИКТ",
        "button_record": "ЗАП",
        "button_asr": "АСР",
        "button_punct": "ПУНКТ",
        "button_text": "ТЕКСТ",
        "button_busy": "ЗАНЯТ",
        "button_ok": "ОК",
        "button_copy": "КОПИЯ",
        "button_paste": "ВСТ",
        "button_empty": "ПУСТО",
        "button_error": "ОШИБ",
        "assign": "Назначить",
        "press_keys": "Нажмите клавиши...",
        "apply": "Применить",
        "save": "Сохранить",
        "cancel": "Отмена",
        "unsaved_settings": "Несохраненные настройки",
        "save_settings_before_closing": "Сохранить настройки перед закрытием?",
        "load_error": "Ошибка загрузки",
        "error": "Ошибка",
        "Loading models": "Загрузка моделей",
        "Downloading ASR": "Загрузка ASR",
        "Loading ASR": "Запуск ASR",
        "Downloading punct": "Загрузка пунктуации",
        "Converting punct": "Конвертация пунктуации",
        "Loading punct": "Запуск пунктуации",
        "Ready": "Готово",
        "Starting": "Запуск",
        "Still loading": "Еще загружается",
        "Recording": "Запись",
        "Transcribing": "Распознавание",
        "Pasted": "Вставлено",
        "Copied": "Скопировано",
        "Copied - paste manually": "Скопировано - вставьте вручную",
        "No audio": "Нет звука",
        "Too short": "Слишком коротко",
        "No speech": "Речь не найдена",
        "Debug copied": "Диагностика скопирована",
        "Hotkey captured": "Клавиша назначена",
        "Hotkey capture canceled": "Назначение отменено",
        "Press hotkey": "Нажмите сочетание",
        "Finish hotkey capture": "Завершите назначение",
        "Bad sample rate": "Неверная частота",
        "Bad hotkey": "Неверная клавиша",
        "Bad overlay key": "Неверная клавиша кнопки",
        "Hotkey conflict": "Конфликт клавиш",
        "Startup error": "Ошибка автозапуска",
        "Settings saved": "Настройки сохранены",
    },
}

CHOICE_TRANSLATION_KEYS = {
    "mode": [
        ("hold", "mode_hold"),
        ("toggle", "mode_toggle"),
    ],
    "overlay_size": [
        ("small", "overlay_size_small"),
        ("medium", "overlay_size_medium"),
        ("large", "overlay_size_large"),
    ],
    "overlay_details": [
        ("button", "overlay_details_button"),
        ("status", "overlay_details_status"),
        ("full", "overlay_details_full"),
    ],
}


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
        "ui_language": "en",
        "mode": "hold",
        "dictation_hotkey": "f8",
        "overlay_hotkey": "ctrl+alt+shift+d",
        "input_device_index": choose_default_device_index(),
        "sample_rate": 0,
        "channels": 1,
        "use_punctuation": True,
        "punct_device": "NPU",
        "auto_paste": True,
        "use_context": True,
        "context_chars": 320,
        "append_space": True,
        "start_with_windows": False,
        "overlay_visible": True,
        "overlay_x": None,
        "overlay_y": None,
        "overlay_size": "medium",
        "overlay_details": "full",
        "overlay_opacity": 1.0,
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


def normalize_ui_language(value):
    return value if value in TRANSLATIONS else "en"


def startup_folder():
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_shortcut_path():
    return startup_folder() / f"{APP_NAME}.lnk"


def startup_target_python():
    venv_pythonw = repo_root() / ".venv" / "Scripts" / "pythonw.exe"
    if venv_pythonw.exists():
        return venv_pythonw
    return Path(sys.executable)


def is_startup_enabled():
    return startup_shortcut_path().exists()


def set_startup_enabled(enabled):
    if os.name != "nt":
        return False

    shortcut_path = startup_shortcut_path()
    try:
        if not enabled:
            shortcut_path.unlink(missing_ok=True)
            return True

        import comtypes.client

        shortcut_path.parent.mkdir(parents=True, exist_ok=True)
        target = startup_target_python()
        script = repo_root() / "tools" / "voice_dictation_app.py"
        shell = comtypes.client.CreateObject("WScript.Shell", dynamic=True)
        shortcut = shell.CreateShortcut(str(shortcut_path))
        shortcut.TargetPath = str(target)
        shortcut.Arguments = f'"{script}"'
        shortcut.WorkingDirectory = str(repo_root())
        shortcut.IconLocation = str(target)
        shortcut.Description = APP_NAME
        shortcut.Save()
        return True
    except Exception as exc:
        log_debug(f"startup shortcut error={type(exc).__name__}")
        return False


def clamp_overlay_opacity(value):
    try:
        opacity = float(value)
    except (TypeError, ValueError):
        return 1.0
    return min(max(opacity, 0.3), 1.0)


def format_elapsed(seconds):
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def log_debug(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with (repo_root() / "voice_dictation.log").open("a", encoding="utf-8") as file:
            file.write(f"{timestamp} {message}\n")
    except OSError:
        pass


def token_from_virtual_key(vk):
    try:
        vk = int(vk)
    except (TypeError, ValueError):
        return None

    if 0x30 <= vk <= 0x39:
        return str(vk - 0x30)
    if 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    if 0x60 <= vk <= 0x69:
        return str(vk - 0x60)
    if 0x70 <= vk <= 0x87:
        return f"f{vk - 0x6F}"
    if vk == 0x0D:
        return "enter"
    if vk == 0x1B:
        return "esc"
    if vk == 0x20:
        return "space"
    return None


def key_to_token(key):
    if isinstance(key, keyboard.KeyCode):
        vk_token = token_from_virtual_key(getattr(key, "vk", None))
        if vk_token:
            return vk_token
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


MODIFIER_TOKENS = {"ctrl", "alt", "shift", "win"}
TOKEN_LABELS = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win",
    "esc": "Esc",
    "enter": "Enter",
    "space": "Space",
}


def format_hotkey_tokens(tokens):
    ordered = []
    for token in ("ctrl", "alt", "shift", "win"):
        if token in tokens:
            ordered.append(token)
    ordered.extend(sorted(token for token in tokens if token not in MODIFIER_TOKENS))
    return "+".join(TOKEN_LABELS.get(token, token.upper() if token.startswith("f") else token) for token in ordered)


def tk_key_to_token(event):
    aliases = {
        "control_l": "ctrl",
        "control_r": "ctrl",
        "shift_l": "shift",
        "shift_r": "shift",
        "alt_l": "alt",
        "alt_r": "alt",
        "menu": "alt",
        "win_l": "win",
        "win_r": "win",
        "super_l": "win",
        "super_r": "win",
        "escape": "esc",
        "return": "enter",
    }
    keysym = (event.keysym or "").lower()
    if keysym in aliases:
        return aliases[keysym]
    vk_token = token_from_virtual_key(getattr(event, "keycode", None))
    if vk_token:
        return vk_token
    if event.char and len(event.char) == 1 and event.char.isprintable():
        return event.char.lower()
    return aliases.get(keysym, keysym)


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


def normalize_punctuation_context(text, max_chars=320):
    text = re.sub(r"\s+", " ", str(text or ""))
    if not text.strip():
        return ""
    if len(text) > max_chars:
        text = text[-max_chars:]

    sentence_breaks = list(re.finditer("[.!?\\u2026]+[\"')\\]]?\\s+", text))
    if sentence_breaks and sentence_breaks[-1].end() < len(text.rstrip()):
        return text[sentence_breaks[-1].end() :].lstrip()
    return text.lstrip()


def token_trailing_punctuation(token):
    match = re.search(r"([^\w\s]+)$", str(token or ""), flags=re.UNICODE)
    return match.group(1) if match else ""


def text_ends_sentence(text):
    return bool(re.search("[.!?\\u2026]+[\"')\\]]*$", str(text or "").rstrip()))


def lowercase_first_alpha(text):
    text = str(text or "")
    for index, char in enumerate(text):
        if char.isalpha():
            return f"{text[:index]}{char.lower()}{text[index + 1:]}"
    return text


def boundary_prefix_from_context(context, restored_tokens, raw_token_count):
    context = str(context or "")
    context_tokens = context.rstrip().split()
    boundary_index = len(restored_tokens) - raw_token_count - 1
    if not context_tokens or boundary_index < 0:
        return ""

    original_suffix = token_trailing_punctuation(context_tokens[-1])
    restored_suffix = token_trailing_punctuation(restored_tokens[boundary_index])
    if restored_suffix and restored_suffix != original_suffix:
        return f"{restored_suffix} "
    return " " if context and not context[-1].isspace() else ""


def inserted_text_from_context(raw_text, restored_with_context, context):
    raw_tokens = str(raw_text or "").split()
    if not raw_tokens or not context:
        return str(restored_with_context or "").strip()

    restored_tokens = str(restored_with_context or "").split()
    raw_token_count = len(raw_tokens)
    if len(restored_tokens) < raw_token_count:
        return str(restored_with_context or "").strip()

    tail = " ".join(restored_tokens[-raw_token_count:])
    prefix = boundary_prefix_from_context(context, restored_tokens, raw_token_count)
    boundary = prefix.strip()
    if boundary and tail.startswith(boundary):
        tail = tail[len(boundary) :].lstrip()
    if context and not text_ends_sentence(context) and not text_ends_sentence(prefix):
        tail = lowercase_first_alpha(tail)
    return f"{prefix}{tail}"


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
        self.keyboard_controller = keyboard.Controller()
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

    def context_before_cursor(self, max_chars=320):
        if self.auto is None:
            return ""

        try:
            import comtypes

            comtypes.CoInitialize()
            focused = self.find_text_control(self.auto.GetFocusedControl())
            if focused and int(focused.ProcessId) != self.current_pid:
                self.last_input = focused
            control = focused or self.last_input
            if control is None:
                log_debug("uia context skipped=no-control")
                return ""
            if int(control.ProcessId) == self.current_pid:
                log_debug("uia context skipped=self")
                return ""

            control_type = getattr(control, "ControlTypeName", "")
            pattern = control.GetTextPattern()
            if pattern is None:
                log_debug(f"uia context skipped=no-text-pattern type={control_type}")
                return self.clipboard_line_context(max_chars)

            selections = pattern.GetSelection()
            if not selections:
                log_debug(f"uia context skipped=no-selection type={control_type}")
                return self.clipboard_line_context(max_chars)

            cursor = selections[0]
            context_range = cursor.Clone()
            context_range.ExpandToEnclosingUnit(self.auto.TextUnit.Paragraph, waitTime=0)
            context_range.MoveEndpointByRange(
                self.auto.TextPatternRangeEndpoint.End,
                cursor,
                self.auto.TextPatternRangeEndpoint.Start,
                waitTime=0,
            )
            text = context_range.GetText(-1) or ""
            if "\ufffc" in text:
                log_debug(f"uia context rejected=object-char type={control_type} chars={len(text)}")
                return ""
            if len(text) > max_chars * 3:
                log_debug(f"uia context rejected=too-wide type={control_type} chars={len(text)}")
                return ""
            if len(text) > max_chars:
                text = text[-int(max_chars) :]
            log_debug(f"uia context type={control_type} chars={len(text)}")
            return text
        except Exception as exc:
            log_debug(f"uia context error={type(exc).__name__}")
            return ""

    def clipboard_line_context(self, max_chars=320):
        try:
            previous_clipboard = pyperclip.paste()
        except Exception:
            previous_clipboard = ""

        try:
            pyperclip.copy("")
            self.keyboard_controller.press(keyboard.Key.shift)
            self.keyboard_controller.press(keyboard.Key.home)
            self.keyboard_controller.release(keyboard.Key.home)
            self.keyboard_controller.release(keyboard.Key.shift)
            time.sleep(0.04)

            self.keyboard_controller.press(keyboard.Key.ctrl)
            self.keyboard_controller.press("c")
            self.keyboard_controller.release("c")
            self.keyboard_controller.release(keyboard.Key.ctrl)
            time.sleep(0.06)

            text = pyperclip.paste() or ""
            if text:
                self.keyboard_controller.press(keyboard.Key.right)
                self.keyboard_controller.release(keyboard.Key.right)
                time.sleep(0.02)

            if len(text) > max_chars:
                text = text[-int(max_chars) :]
            log_debug(f"clipboard context chars={len(text)}")
            return text
        except Exception as exc:
            log_debug(f"clipboard context error={type(exc).__name__}")
            return ""
        finally:
            try:
                pyperclip.copy(previous_clipboard)
            except Exception:
                pass


class HotkeyManager:
    def __init__(self, cfg, dispatch):
        self.cfg = cfg
        self.dispatch = dispatch
        self.pressed = set()
        self.dictation_down = False
        self.overlay_down = False
        self.suspended = False
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

    def set_suspended(self, suspended):
        self.suspended = suspended
        self.pressed.clear()
        self.dictation_down = False
        self.overlay_down = False

    def hotkeys(self):
        return parse_hotkey(self.cfg["dictation_hotkey"]), parse_hotkey(self.cfg["overlay_hotkey"])

    def on_press(self, key):
        if self.suspended:
            return

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
        if self.suspended:
            return

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
    def __init__(self, cfg, status_callback, text_callback, focus_callback=None, context_callback=None):
        self.cfg = cfg
        self.status_callback = status_callback
        self.text_callback = text_callback
        self.focus_callback = focus_callback
        self.context_callback = context_callback
        self.asr = None
        self.punct = None
        self.loaded = False
        self.loading = False
        self.recording = False
        self.transcribing = False
        self.stream = None
        self.sample_rate = None
        self.audio_blocks = []
        self.recording_context = ""
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
            load_start = time.perf_counter()
            log_debug("load start")
            ensure_asr_model(self.set_status)
            self.set_status("Loading ASR")
            asr_start = time.perf_counter()
            asr = onnx_asr.load_model("gigaam-v3-ctc", asr_model_dir(), quantization="int8")
            log_debug(f"load asr done seconds={time.perf_counter() - asr_start:.3f}")

            punct = None
            if self.cfg.get("use_punctuation", True):
                self.set_status("Loading punct")
                log_debug("load punct import start")
                from rupunct_restore import RUPunctRestorer
                log_debug("load punct import done")

                log_debug("load punct ensure start")
                ensure_punct_model(self.set_status)
                log_debug("load punct ensure done")
                punct_start = time.perf_counter()
                punct = RUPunctRestorer(
                    default_punct_model_dir(),
                    self.cfg.get("punct_device", "NPU"),
                    cache_dir=repo_root() / "models" / "openvino" / "cache",
                )
                log_debug(f"load punct done seconds={time.perf_counter() - punct_start:.3f}")

            with self.lock:
                self.asr = asr
                self.punct = punct
                self.loaded = True
                self.loading = False
            log_debug(f"load ready seconds={time.perf_counter() - load_start:.3f}")
            self.set_status("Ready")
        except Exception as exc:
            with self.lock:
                self.loading = False
            log_debug(f"load error type={type(exc).__name__}")
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
            self.recording_context = self.context_before_cursor()

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
            self.recording_context = ""

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
                context = self.recording_context or self.context_before_cursor()
                if context:
                    restored = self.punct.restore(f"{context} {raw_text}".strip())
                    final_text = inserted_text_from_context(raw_text, restored, context)
                else:
                    final_text = self.punct.restore(raw_text)
                punct_sec = time.perf_counter() - start

            if self.cfg.get("append_space", False) and final_text:
                final_text = final_text.rstrip() + " "

            if final_text:
                self.text_callback(raw_text, final_text, duration, asr_sec, punct_sec)
                if self.cfg.get("auto_paste", True):
                    if self.paste_text(final_text):
                        self.set_status("Pasted")
                    else:
                        self.set_status("Copied - paste manually")
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
                self.recording_context = ""

    def context_before_cursor(self):
        if not self.cfg.get("use_context", True) or self.context_callback is None:
            return ""
        try:
            max_chars = int(self.cfg.get("context_chars", 320) or 320)
        except (TypeError, ValueError):
            max_chars = 320
        context = normalize_punctuation_context(self.context_callback(max_chars), max_chars)
        if context:
            log_debug(f"punct context normalized_chars={len(context)}")
        return context

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

        try:
            self.keyboard.press(keyboard.Key.ctrl)
            self.keyboard.press("v")
            self.keyboard.release("v")
            self.keyboard.release(keyboard.Key.ctrl)
            log_debug("paste fallback=pynput")
            return True
        except Exception as exc:
            log_debug(f"paste failed fallback_error={type(exc).__name__}")
            return False

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
        self.cfg["ui_language"] = normalize_ui_language(self.cfg.get("ui_language", "en"))
        self.cfg["start_with_windows"] = is_startup_enabled()
        self.event_queue = queue.Queue()
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_overlay)
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.root.configure(bg="#20242b")
        self.apply_overlay_opacity()

        self.status_var = tk.StringVar(value="Loading models")
        self.current_status = "Loading models"
        self.current_display_status = "Loading models"
        self.last_text_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value=self.cfg.get("mode", "hold"))
        self.settings_i18n_widgets = []
        self.settings_i18n_choices = []
        self.progress_running = False
        self.tray_icon = None
        self.recording_started_at = None
        self.transcribing_started_at = None
        self.status_tick_after_id = None
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
            context_callback=self.context_before_cursor,
        )
        self.hotkeys = HotkeyManager(self.cfg, self.dispatch)

        self._build_overlay()
        self.update_status("Loading models")
        self._position_overlay()
        self.foreground_tracker.make_no_activate(self.root.winfo_id())
        self._position_overlay()
        self._build_menu()
        self.start_tray_icon()

        if not self.cfg.get("overlay_visible", True):
            self.root.withdraw()

        self.root.after(100, self.poll_events)
        self.root.after(100, self.track_foreground)
        self.root.after(50, self.engine.load_async)
        self.hotkeys.start()

    def t(self, key):
        language = normalize_ui_language(self.cfg.get("ui_language", "en"))
        return TRANSLATIONS.get(language, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"].get(key, key))

    def localize_status(self, status):
        if status.startswith("Load error: "):
            return f"{self.t('load_error')}: {status.split(': ', 1)[1]}"
        if status.startswith("Error: "):
            return f"{self.t('error')}: {status.split(': ', 1)[1]}"
        return self.t(status)

    def choice_label(self, group, value):
        for code, key in CHOICE_TRANSLATION_KEYS.get(group, []):
            if code == value:
                return self.t(key)
        return value

    def choice_labels(self, group):
        return [self.t(key) for _, key in CHOICE_TRANSLATION_KEYS.get(group, [])]

    def choice_value(self, group, label, default=None):
        label = str(label)
        choices = CHOICE_TRANSLATION_KEYS.get(group, [])
        for code, key in choices:
            if label == code:
                return code
            if any(label == translations.get(key) for translations in TRANSLATIONS.values()):
                return code
        if default is not None:
            return default
        return choices[0][0] if choices else label

    def _build_overlay(self):
        self.frame = tk.Frame(self.root, bg="#20242b", padx=8, pady=7)
        self.frame.pack(fill="both", expand=True)

        self.button = tk.Button(
            self.frame,
            text=self.t("button_dict"),
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

        self.apply_overlay_layout()

        for widget in (self.root, self.frame, self.button, self.status_label, self.hotkey_label, self.progress):
            widget.bind("<Button-3>", self.show_menu)
            widget.bind("<ButtonPress-1>", self.on_overlay_press)
            widget.bind("<B1-Motion>", self.on_overlay_motion)
            widget.bind("<ButtonRelease-1>", self.on_overlay_release)

    def overlay_size_profile(self):
        profiles = {
            "small": {
                "padx": 8,
                "pady": 7,
                "button_width": 8,
                "button_height": 2,
                "button_font": ("Segoe UI", 10, "bold"),
                "status_font": ("Segoe UI", 8),
                "hotkey_font": ("Segoe UI", 7),
                "progress_length": 86,
            },
            "medium": {
                "padx": 10,
                "pady": 8,
                "button_width": 10,
                "button_height": 3,
                "button_font": ("Segoe UI", 13, "bold"),
                "status_font": ("Segoe UI", 10),
                "hotkey_font": ("Segoe UI", 9),
                "progress_length": 108,
            },
            "large": {
                "padx": 12,
                "pady": 10,
                "button_width": 12,
                "button_height": 3,
                "button_font": ("Segoe UI", 17, "bold"),
                "status_font": ("Segoe UI", 13),
                "hotkey_font": ("Segoe UI", 11),
                "progress_length": 128,
            },
        }
        return profiles.get(self.cfg.get("overlay_size", "medium"), profiles["medium"])

    def apply_overlay_opacity(self, opacity=None):
        opacity = clamp_overlay_opacity(self.cfg.get("overlay_opacity", 1.0) if opacity is None else opacity)
        try:
            self.root.attributes("-alpha", opacity)
        except tk.TclError:
            pass

    def overlay_details_mode(self):
        value = self.cfg.get("overlay_details", "full")
        return value if value in {"button", "status", "full"} else "full"

    def apply_overlay_layout(self):
        profile = self.overlay_size_profile()
        self.frame.configure(padx=profile["padx"], pady=profile["pady"])
        self.button.configure(
            width=profile["button_width"],
            height=profile["button_height"],
            font=profile["button_font"],
        )
        self.status_label.configure(font=profile["status_font"])
        self.hotkey_label.configure(font=profile["hotkey_font"])
        self.progress.configure(length=profile["progress_length"])

        details = self.overlay_details_mode()
        if details in {"status", "full"}:
            if not self.status_label.winfo_ismapped():
                self.status_label.pack(fill="x", pady=(5, 0))
        else:
            self.status_label.pack_forget()

        if details == "full":
            if not self.hotkey_label.winfo_ismapped():
                self.hotkey_label.pack(fill="x")
        else:
            self.hotkey_label.pack_forget()

        self.update_status(self.current_status)

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
        self.menu = tk.Menu(
            self.root,
            tearoff=0,
            font=("Segoe UI", 12),
            borderwidth=2,
            activeborderwidth=2,
        )
        self.menu.add_command(label=self.t("start_stop"), command=self.engine.toggle_recording)
        self.menu.add_command(label=self.t("settings"), command=self.open_settings)
        self.menu.add_command(label=self.t("hide_overlay"), command=self.hide_overlay)
        self.menu.add_command(label=self.t("copy_debug_info"), command=self.copy_debug_info)
        self.menu.add_separator()
        self.menu.add_command(label=self.t("exit"), command=self.exit_app)

    def show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def make_tray_image(self):
        if Image is None or ImageDraw is None:
            return None

        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((6, 6, 58, 58), radius=14, fill="#2864d8")
        draw.ellipse((22, 14, 42, 38), fill="white")
        draw.rounded_rectangle((27, 36, 37, 49), radius=4, fill="white")
        draw.rounded_rectangle((20, 48, 44, 53), radius=2, fill="white")
        return image

    def start_tray_icon(self):
        if pystray is None:
            log_debug("tray unavailable: pystray not installed")
            return

        image = self.make_tray_image()
        if image is None:
            log_debug("tray unavailable: icon image backend missing")
            return

        try:
            self.tray_icon = pystray.Icon(
                "local_voice_dictation",
                image,
                self.tray_title(),
                self.build_tray_menu(),
            )
            self.tray_icon.run_detached()
        except Exception as exc:
            self.tray_icon = None
            log_debug(f"tray start error={type(exc).__name__}")

    def build_tray_menu(self):
        return pystray.Menu(
            pystray.MenuItem(lambda item: f"{self.t('status_prefix')}: {self.current_display_status}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.t("show_overlay"), lambda: self.dispatch("show_overlay"), default=True),
            pystray.MenuItem(self.t("hide_overlay"), lambda: self.dispatch("hide_overlay")),
            pystray.MenuItem(self.t("settings"), lambda: self.dispatch("open_settings")),
            pystray.MenuItem(self.t("copy_debug_info"), lambda: self.dispatch("copy_debug_info")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.t("quit"), lambda: self.dispatch("exit_app")),
        )

    def tray_title(self):
        status = self.current_display_status[:80]
        return f"{APP_NAME}: {status}"

    def update_tray_status(self):
        if not self.tray_icon:
            return
        try:
            self.tray_icon.title = self.tray_title()
        except Exception as exc:
            log_debug(f"tray update error={type(exc).__name__}")

    def refresh_static_ui_text(self):
        self.root.title(APP_NAME)
        self._build_menu()
        if self.tray_icon and pystray is not None:
            try:
                self.tray_icon.menu = self.build_tray_menu()
            except Exception as exc:
                log_debug(f"tray menu language error={type(exc).__name__}")
        self.refresh_settings_window_text()
        self.update_status(self.current_status)

    def refresh_settings_window_text(self):
        if not hasattr(self, "settings_window") or not self.settings_window.winfo_exists():
            self.settings_i18n_widgets = []
            self.settings_i18n_choices = []
            return

        self.settings_window.title(f"{APP_NAME} {self.t('settings_title')}")
        for widget, key in self.settings_i18n_widgets:
            try:
                if widget.winfo_exists():
                    widget.configure(text=self.t(key))
            except tk.TclError:
                pass
        for combobox, variable, group, default in self.settings_i18n_choices:
            try:
                if not combobox.winfo_exists():
                    continue
                value = self.choice_value(group, variable.get(), self.cfg.get(group, default))
                combobox.configure(values=self.choice_labels(group))
                variable.set(self.choice_label(group, value))
            except tk.TclError:
                pass

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

    def context_before_cursor(self, max_chars=320):
        if not self.cfg.get("use_context", True):
            return ""
        return self.input_tracker.context_before_cursor(max_chars)

    def collect_debug_info(self):
        log_path = repo_root() / "voice_dictation.log"
        log_tail = []
        if log_path.exists():
            try:
                log_tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
            except OSError as exc:
                log_tail = [f"log read error: {type(exc).__name__}"]

        info = {
            "app": APP_NAME,
            "status": self.current_display_status,
            "python": sys.version,
            "platform": platform.platform(),
            "repo_root": str(repo_root()),
            "config_path": str(config_path()),
            "config": self.cfg,
            "models": {
                "asr_dir_exists": asr_model_dir().exists(),
                "punct_dir_exists": default_punct_model_dir().exists(),
            },
            "raw_status": self.current_status,
            "tray_available": pystray is not None,
            "tray_running": self.tray_icon is not None,
            "overlay_state": self.root.state(),
            "last_text": self.last_text_var.get(),
            "log_tail": log_tail,
        }
        return json.dumps(info, ensure_ascii=False, indent=2)

    def copy_debug_info(self):
        pyperclip.copy(self.collect_debug_info())
        self.update_status("Debug copied")

    def handle_action(self, action):
        if action == "toggle_overlay":
            self.toggle_overlay()
        elif action == "show_overlay":
            self.show_overlay()
        elif action == "hide_overlay":
            self.hide_overlay()
        elif action == "open_settings":
            self.open_settings()
        elif action == "copy_debug_info":
            self.copy_debug_info()
        elif action == "exit_app":
            self.exit_app()
        elif action == "start_recording":
            self.engine.start_recording()
        elif action == "stop_recording":
            self.engine.stop_recording()
        elif action == "toggle_recording":
            self.engine.toggle_recording()

    def set_display_status(self, status):
        self.current_display_status = status
        self.status_var.set(status)
        self.update_tray_status()

    def dynamic_status_text(self):
        now = time.perf_counter()
        if self.current_status == "Recording" and self.recording_started_at is not None:
            return f"{self.t('Recording')} {format_elapsed(now - self.recording_started_at)}"
        if self.current_status == "Transcribing" and self.transcribing_started_at is not None:
            return f"{self.t('Transcribing')} {format_elapsed(now - self.transcribing_started_at)}"
        return self.localize_status(self.current_status)

    def schedule_status_tick(self):
        if self.status_tick_after_id is None:
            self.status_tick_after_id = self.root.after(500, self.refresh_dynamic_status)

    def refresh_dynamic_status(self):
        self.status_tick_after_id = None
        if self.current_status not in {"Recording", "Transcribing"}:
            return
        self.set_display_status(self.dynamic_status_text())
        self.schedule_status_tick()

    def update_status(self, status):
        previous_status = self.current_status
        self.current_status = status

        if status == "Recording":
            if previous_status != "Recording" or self.recording_started_at is None:
                self.recording_started_at = time.perf_counter()
            self.transcribing_started_at = None
            self.set_display_status(self.dynamic_status_text())
            self.schedule_status_tick()
        elif status == "Transcribing":
            if previous_status != "Transcribing" or self.transcribing_started_at is None:
                self.transcribing_started_at = time.perf_counter()
            self.recording_started_at = None
            self.set_display_status(self.dynamic_status_text())
            self.schedule_status_tick()
        else:
            self.recording_started_at = None
            self.transcribing_started_at = None
            self.set_display_status(self.localize_status(status))

        busy = (
            status.startswith("Downloading")
            or status.startswith("Converting")
            or status.startswith("Loading")
            or status in {"Still loading", "Transcribing"}
        )
        show_progress = busy and self.overlay_details_mode() != "button"
        if show_progress and not self.progress_running:
            self.progress.pack(fill="x", pady=(5, 0))
            self.progress.start(12)
            self.progress_running = True
        elif not show_progress and self.progress_running:
            self.progress.stop()
            self.progress.pack_forget()
            self.progress_running = False

        if status == "Recording":
            self.button.configure(text=self.t("button_record"), bg="#b83030", activebackground="#982727")
        elif status == "Loading ASR":
            self.button.configure(text=self.t("button_asr"), bg="#81612b", activebackground="#6d5124")
        elif status == "Loading punct":
            self.button.configure(text=self.t("button_punct"), bg="#81612b", activebackground="#6d5124")
        elif status == "Transcribing":
            self.button.configure(text=self.t("button_text"), bg="#81612b", activebackground="#6d5124")
        elif busy:
            self.button.configure(text=self.t("button_busy"), bg="#81612b", activebackground="#6d5124")
        elif status == "Pasted":
            self.button.configure(text=self.t("button_ok"), bg="#267d45", activebackground="#206b3b")
        elif status == "Copied":
            self.button.configure(text=self.t("button_copy"), bg="#2b7281", activebackground="#245f6c")
        elif status.startswith("Copied - paste"):
            self.button.configure(text=self.t("button_paste"), bg="#b85528", activebackground="#98441f")
        elif status in {"No audio", "Too short", "No speech"}:
            self.button.configure(text=self.t("button_empty"), bg="#5f6773", activebackground="#505762")
        elif status.startswith("Error") or status.startswith("Load error") or status in {
            "Bad hotkey",
            "Bad overlay key",
            "Hotkey conflict",
            "Startup error",
        }:
            self.button.configure(text=self.t("button_error"), bg="#9f3030", activebackground="#832929")
        else:
            self.button.configure(text=self.t("button_dict"), bg="#2864d8", activebackground="#1f55bd")

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
            self.show_overlay()
        else:
            self.hide_overlay()

    def show_overlay(self):
        self.cfg["overlay_visible"] = True
        save_config(self.cfg)
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.apply_overlay_opacity()
        self._position_overlay()

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
        self.settings_i18n_widgets = []
        self.settings_i18n_choices = []
        win.title(f"{APP_NAME} {self.t('settings_title')}")
        win.attributes("-topmost", True)
        win.resizable(True, True)
        win.configure(padx=24, pady=20)
        win.minsize(780, 560)
        win.columnconfigure(1, weight=1)

        settings_font = ("Segoe UI", 12)
        settings_small_font = ("Segoe UI", 10)
        settings_style = ttk.Style(win)
        settings_style.configure("TLabel", font=settings_font)
        settings_style.configure("TCheckbutton", font=settings_font, padding=(0, 4))
        settings_style.configure("TButton", font=settings_font, padding=(12, 6))
        win.option_add("*TCombobox*Listbox.font", settings_font)

        mode = tk.StringVar(value=self.choice_label("mode", self.cfg.get("mode", "hold")))
        ui_language = tk.StringVar(value=UI_LANGUAGE_NAMES[normalize_ui_language(self.cfg.get("ui_language", "en"))])
        dict_hotkey = tk.StringVar(value=self.cfg.get("dictation_hotkey", "f8"))
        overlay_hotkey = tk.StringVar(value=self.cfg.get("overlay_hotkey", "ctrl+alt+shift+d"))
        overlay_size = tk.StringVar(value=self.choice_label("overlay_size", self.cfg.get("overlay_size", "medium")))
        overlay_details = tk.StringVar(value=self.choice_label("overlay_details", self.cfg.get("overlay_details", "full")))
        overlay_opacity = tk.DoubleVar(value=clamp_overlay_opacity(self.cfg.get("overlay_opacity", 1.0)) * 100)
        overlay_opacity_label = tk.StringVar()
        sample_rate = tk.StringVar(value=str(self.cfg.get("sample_rate", 0)))
        use_punctuation = tk.BooleanVar(value=bool(self.cfg.get("use_punctuation", True)))
        auto_paste = tk.BooleanVar(value=bool(self.cfg.get("auto_paste", True)))
        use_context = tk.BooleanVar(value=bool(self.cfg.get("use_context", True)))
        append_space = tk.BooleanVar(value=bool(self.cfg.get("append_space", False)))
        start_with_windows = tk.BooleanVar(value=is_startup_enabled())
        dirty = tk.BooleanVar(value=False)

        def remember_i18n(widget, key):
            self.settings_i18n_widgets.append((widget, key))
            return widget

        def remember_choice(combobox, variable, group, default):
            self.settings_i18n_choices.append((combobox, variable, group, default))
            return combobox

        def i18n_label(parent, key, **kwargs):
            return remember_i18n(ttk.Label(parent, text=self.t(key), **kwargs), key)

        def i18n_button(parent, key, **kwargs):
            return remember_i18n(ttk.Button(parent, text=self.t(key), **kwargs), key)

        def i18n_checkbutton(parent, key, **kwargs):
            return remember_i18n(ttk.Checkbutton(parent, text=self.t(key), **kwargs), key)

        def clear_i18n_registry(event):
            if event.widget == win:
                self.settings_i18n_widgets = []
                self.settings_i18n_choices = []

        win.bind("<Destroy>", clear_i18n_registry, add="+")

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

        def mark_dirty(*_):
            dirty.set(True)

        for variable in (
            mode,
            ui_language,
            dict_hotkey,
            overlay_hotkey,
            overlay_size,
            overlay_details,
            overlay_opacity,
            selected_device,
            sample_rate,
            use_punctuation,
            auto_paste,
            use_context,
            append_space,
            start_with_windows,
        ):
            variable.trace_add("write", mark_dirty)

        def update_opacity_label(*_):
            overlay_opacity_label.set(f"{int(round(overlay_opacity.get()))}%")

        overlay_opacity.trace_add("write", update_opacity_label)
        update_opacity_label()

        capture_state = {
            "variable": None,
            "previous": "",
            "tokens": set(),
        }

        def stop_hotkey_capture():
            win.unbind("<KeyPress>")
            win.unbind("<KeyRelease>")
            self.hotkeys.set_suspended(False)
            capture_state["variable"] = None
            capture_state["previous"] = ""
            capture_state["tokens"] = set()

        def finish_hotkey_capture(tokens):
            variable = capture_state["variable"]
            if variable is not None and tokens:
                variable.set(format_hotkey_tokens(tokens))
            stop_hotkey_capture()
            self.update_status("Hotkey captured")

        def cancel_hotkey_capture():
            variable = capture_state["variable"]
            if variable is not None:
                variable.set(capture_state["previous"])
            stop_hotkey_capture()
            self.update_status("Hotkey capture canceled")

        def capture_keypress(event):
            token = tk_key_to_token(event)
            if not token:
                return "break"
            if token == "esc":
                cancel_hotkey_capture()
                return "break"

            capture_state["tokens"].add(token)
            variable = capture_state["variable"]
            if variable is not None:
                variable.set(format_hotkey_tokens(capture_state["tokens"]))

            if token not in MODIFIER_TOKENS:
                finish_hotkey_capture(capture_state["tokens"])
            return "break"

        def capture_keyrelease(event):
            token = tk_key_to_token(event)
            if token in MODIFIER_TOKENS and capture_state["tokens"] == {token}:
                finish_hotkey_capture(capture_state["tokens"])
            return "break"

        def start_hotkey_capture(variable, entry):
            if capture_state["variable"] is not None:
                cancel_hotkey_capture()
            capture_state["variable"] = variable
            capture_state["previous"] = variable.get()
            capture_state["tokens"] = set()
            variable.set(self.t("press_keys"))
            self.hotkeys.set_suspended(True)
            win.bind("<KeyPress>", capture_keypress)
            win.bind("<KeyRelease>", capture_keyrelease)
            entry.focus_set()
            win.focus_force()
            self.update_status("Press hotkey")

        def current_values():
            if capture_state["variable"] is not None:
                self.update_status("Finish hotkey capture")
                return None

            try:
                sample_rate_value = int(sample_rate.get() or 0)
            except ValueError:
                self.update_status("Bad sample rate")
                return None

            return {
                "mode": self.choice_value("mode", mode.get(), "hold"),
                "ui_language": normalize_ui_language(UI_LANGUAGE_BY_NAME.get(ui_language.get(), "en")),
                "dictation_hotkey": dict_hotkey.get(),
                "overlay_hotkey": overlay_hotkey.get(),
                "overlay_size": self.choice_value("overlay_size", overlay_size.get(), "medium"),
                "overlay_details": self.choice_value("overlay_details", overlay_details.get(), "full"),
                "overlay_opacity": clamp_overlay_opacity(overlay_opacity.get() / 100),
                "input_device_index": int(selected_device.get().split(":", 1)[0]) if selected_device.get() else None,
                "sample_rate": sample_rate_value,
                "use_punctuation": bool(use_punctuation.get()),
                "auto_paste": bool(auto_paste.get()),
                "use_context": bool(use_context.get()),
                "append_space": bool(append_space.get()),
                "start_with_windows": bool(start_with_windows.get()),
            }

        def apply_settings(close=False):
            values = current_values()
            if values is None:
                return False
            if not self.save_settings(win, values, close=close):
                return False
            dirty.set(False)
            return True

        def close_settings():
            if capture_state["variable"] is not None:
                cancel_hotkey_capture()

            if not dirty.get():
                win.destroy()
                return

            choice = messagebox.askyesnocancel(
                self.t("unsaved_settings"),
                self.t("save_settings_before_closing"),
                parent=win,
            )
            if choice is None:
                return
            if choice:
                apply_settings(close=True)
                return
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", close_settings)

        row = 0
        i18n_label(win, "mode").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        mode_combo = ttk.Combobox(
            win,
            textvariable=mode,
            values=self.choice_labels("mode"),
            state="readonly",
            width=32,
            font=settings_font,
        )
        remember_choice(mode_combo, mode, "mode", "hold").grid(row=row, column=1, sticky="ew", pady=6)

        row += 1
        i18n_label(win, "ui_language").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        ttk.Combobox(
            win,
            textvariable=ui_language,
            values=list(UI_LANGUAGE_NAMES.values()),
            state="readonly",
            width=32,
            font=settings_font,
        ).grid(row=row, column=1, sticky="ew", pady=6)

        row += 1
        i18n_label(win, "overlay_size").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        overlay_size_combo = ttk.Combobox(
            win,
            textvariable=overlay_size,
            values=self.choice_labels("overlay_size"),
            state="readonly",
            width=32,
            font=settings_font,
        )
        remember_choice(overlay_size_combo, overlay_size, "overlay_size", "medium").grid(row=row, column=1, sticky="ew", pady=6)

        row += 1
        i18n_label(win, "overlay_details").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        overlay_details_combo = ttk.Combobox(
            win,
            textvariable=overlay_details,
            values=self.choice_labels("overlay_details"),
            state="readonly",
            width=32,
            font=settings_font,
        )
        remember_choice(overlay_details_combo, overlay_details, "overlay_details", "full").grid(row=row, column=1, sticky="ew", pady=6)

        row += 1
        i18n_label(win, "overlay_opacity").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        opacity_frame = ttk.Frame(win)
        opacity_frame.grid(row=row, column=1, sticky="ew", pady=6)
        opacity_frame.columnconfigure(0, weight=1)
        ttk.Scale(
            opacity_frame,
            from_=30,
            to=100,
            variable=overlay_opacity,
            orient="horizontal",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 12))
        ttk.Label(opacity_frame, textvariable=overlay_opacity_label, width=5).grid(row=0, column=1, sticky="e")

        row += 1
        i18n_label(win, "dictation_hotkey").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        dict_hotkey_frame = ttk.Frame(win)
        dict_hotkey_frame.grid(row=row, column=1, sticky="ew", pady=6)
        dict_hotkey_frame.columnconfigure(0, weight=1)
        dict_hotkey_entry = ttk.Entry(dict_hotkey_frame, textvariable=dict_hotkey, width=36, font=settings_font)
        dict_hotkey_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        i18n_button(
            dict_hotkey_frame,
            "assign",
            command=lambda: start_hotkey_capture(dict_hotkey, dict_hotkey_entry),
        ).grid(row=0, column=1, sticky="e")

        row += 1
        i18n_label(win, "overlay_hotkey").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        overlay_hotkey_frame = ttk.Frame(win)
        overlay_hotkey_frame.grid(row=row, column=1, sticky="ew", pady=6)
        overlay_hotkey_frame.columnconfigure(0, weight=1)
        overlay_hotkey_entry = ttk.Entry(overlay_hotkey_frame, textvariable=overlay_hotkey, width=36, font=settings_font)
        overlay_hotkey_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        i18n_button(
            overlay_hotkey_frame,
            "assign",
            command=lambda: start_hotkey_capture(overlay_hotkey, overlay_hotkey_entry),
        ).grid(row=0, column=1, sticky="e")

        row += 1
        i18n_label(win, "input_device").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        ttk.Combobox(win, textvariable=selected_device, values=device_labels, state="readonly", width=72, font=settings_font).grid(
            row=row, column=1, sticky="ew", pady=6
        )

        row += 1
        i18n_label(win, "sample_rate").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        ttk.Entry(win, textvariable=sample_rate, width=36, font=settings_font).grid(row=row, column=1, sticky="w", pady=6)

        row += 1
        i18n_checkbutton(win, "use_punctuation", variable=use_punctuation).grid(
            row=row, column=1, sticky="w", pady=6
        )

        row += 1
        i18n_checkbutton(win, "paste_into_active_field", variable=auto_paste).grid(
            row=row, column=1, sticky="w", pady=6
        )

        row += 1
        i18n_checkbutton(win, "use_context", variable=use_context).grid(
            row=row, column=1, sticky="w", pady=6
        )

        row += 1
        i18n_checkbutton(win, "append_trailing_space", variable=append_space).grid(
            row=row, column=1, sticky="w", pady=6
        )

        row += 1
        i18n_checkbutton(win, "start_with_windows", variable=start_with_windows).grid(
            row=row, column=1, sticky="w", pady=6
        )

        row += 1
        ttk.Label(win, textvariable=self.last_text_var, wraplength=700, foreground="#555", font=settings_small_font).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(12, 6)
        )

        row += 1
        buttons = ttk.Frame(win)
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=(14, 0))
        i18n_button(buttons, "hide_overlay", command=self.hide_overlay).pack(side="left", padx=(0, 10))
        i18n_button(buttons, "apply", command=lambda: apply_settings(close=False)).pack(side="left", padx=(0, 10))
        i18n_button(buttons, "save", command=lambda: apply_settings(close=True)).pack(side="left", padx=(0, 10))
        i18n_button(buttons, "cancel", command=close_settings).pack(side="left")

    def save_settings(self, win, values, close=True):
        values["ui_language"] = normalize_ui_language(values.get("ui_language", "en"))
        values["dictation_hotkey"] = values["dictation_hotkey"].lower().strip()
        values["overlay_hotkey"] = values["overlay_hotkey"].lower().strip()
        if values.get("overlay_size") not in {"small", "medium", "large"}:
            values["overlay_size"] = "medium"
        if values.get("overlay_details") not in {"button", "status", "full"}:
            values["overlay_details"] = "full"
        values["overlay_opacity"] = clamp_overlay_opacity(values.get("overlay_opacity", 1.0))
        dictation_hotkey = parse_hotkey(values["dictation_hotkey"])
        overlay_hotkey = parse_hotkey(values["overlay_hotkey"])
        if not dictation_hotkey:
            self.update_status("Bad hotkey")
            return False
        if not overlay_hotkey:
            self.update_status("Bad overlay key")
            return False
        if dictation_hotkey == overlay_hotkey:
            self.update_status("Hotkey conflict")
            return False
        if bool(values.get("start_with_windows", False)) != is_startup_enabled():
            if not set_startup_enabled(bool(values.get("start_with_windows", False))):
                self.update_status("Startup error")
                return False
        values["start_with_windows"] = is_startup_enabled()

        self.cfg.update(values)
        save_config(self.cfg)
        self.hotkeys.update_config(self.cfg)
        self.engine.update_config(self.cfg)
        self.hotkey_label.configure(text=self.cfg["dictation_hotkey"].upper())
        self.apply_overlay_layout()
        self.apply_overlay_opacity()
        self._position_overlay()
        self.refresh_static_ui_text()
        self.update_status("Settings saved")
        if close:
            win.destroy()
        return True

    def exit_app(self):
        save_config(self.cfg)
        if self.status_tick_after_id is not None:
            try:
                self.root.after_cancel(self.status_tick_after_id)
            except tk.TclError:
                pass
            self.status_tick_after_id = None
        if self.tray_icon:
            tray_icon = self.tray_icon
            self.tray_icon = None
            try:
                tray_icon.stop()
            except Exception as exc:
                log_debug(f"tray stop error={type(exc).__name__}")
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
