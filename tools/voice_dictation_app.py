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
import tkinter.font as tkfont
from collections import deque
from pathlib import Path
from tkinter import messagebox, ttk
from ctypes import wintypes

import numpy as np
import onnx_asr
import pyperclip
import sounddevice as sd
import soundfile as sf
from pynput import keyboard

from model_setup import ensure_asr_model, ensure_asr_openvino_model, ensure_punct_model

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None
    Image = None
    ImageDraw = None


APP_NAME = "Local Voice Dictation"
CONFIG_VERSION = 1
OVERLAY_TRANSPARENT_COLOR = "#ff00ff"
OVERLAY_PANEL_BG = "#20242b"
OVERLAY_PANEL_BORDER = "#313845"
OVERLAY_TEXT_FG = "#d7deeb"
OVERLAY_HINT_FG = "#8fa0bd"
OVERLAY_SHAPES = {"square", "rounded", "circle"}
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
        "settings_section_general": "General",
        "settings_section_models": "Models",
        "settings_section_overlay": "Overlay",
        "settings_section_hotkeys": "Hotkeys",
        "settings_section_audio": "Audio",
        "settings_section_insertion": "Text insertion",
        "asr_model": "Speech recognition model",
        "asr_device": "Speech recognition device",
        "punct_model": "Punctuation model",
        "punct_device": "Punctuation device",
        "warmup_models": "Warm up models on startup",
        "compare_asr": "Compare ASR CPU/NPU",
        "overlay_size": "Overlay size",
        "overlay_size_small": "Small",
        "overlay_size_medium": "Medium",
        "overlay_size_large": "Large",
        "overlay_shape": "Overlay shape",
        "overlay_shape_square": "Square",
        "overlay_shape_rounded": "Rounded square",
        "overlay_shape_circle": "Circle",
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
        "restore_clipboard_after_paste": "Restore text clipboard after paste",
        "use_context": "Use text before cursor",
        "append_trailing_space": "Add trailing space when appropriate",
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
        "Downloading ASR NPU": "Downloading ASR NPU",
        "Loading ASR": "Loading ASR",
        "Downloading punct": "Downloading punct",
        "Converting punct": "Converting punct",
        "Loading punct dependencies": "Loading punct dependencies",
        "Loading punct": "Loading punct",
        "Warming models": "Warming models",
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
        "settings_section_general": "Основные",
        "settings_section_models": "Модели",
        "settings_section_overlay": "Кнопка",
        "settings_section_hotkeys": "Горячие клавиши",
        "settings_section_audio": "Звук",
        "settings_section_insertion": "Вставка текста",
        "asr_model": "Модель распознавания речи",
        "asr_device": "Устройство распознавания",
        "punct_model": "Модель пунктуации",
        "punct_device": "Устройство пунктуации",
        "warmup_models": "Прогревать модели при запуске",
        "compare_asr": "Сравнивать ASR CPU/NPU",
        "overlay_size": "Размер кнопки",
        "overlay_size_small": "Маленькая",
        "overlay_size_medium": "Средняя",
        "overlay_size_large": "Большая",
        "overlay_shape": "Форма кнопки",
        "overlay_shape_square": "Квадратная",
        "overlay_shape_rounded": "Скругленная",
        "overlay_shape_circle": "Круглая",
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
        "restore_clipboard_after_paste": "Восстанавливать текстовый буфер после вставки",
        "use_context": "Учитывать текст перед курсором",
        "append_trailing_space": "Добавлять пробел после вставки по контексту",
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
        "Downloading ASR NPU": "Загрузка ASR NPU",
        "Loading ASR": "Запуск ASR",
        "Downloading punct": "Загрузка пунктуации",
        "Converting punct": "Конвертация пунктуации",
        "Loading punct dependencies": "Загрузка зависимостей пунктуации",
        "Loading punct": "Запуск пунктуации",
        "Warming models": "Прогрев моделей",
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
    "overlay_shape": [
        ("rounded", "overlay_shape_rounded"),
        ("square", "overlay_shape_square"),
        ("circle", "overlay_shape_circle"),
    ],
    "overlay_details": [
        ("button", "overlay_details_button"),
        ("status", "overlay_details_status"),
        ("full", "overlay_details_full"),
    ],
}


def repo_root():
    return Path(__file__).resolve().parents[1]


class FileTime(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


def filetime_to_int(value):
    return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)


def system_cpu_times():
    if platform.system() != "Windows":
        return None
    idle = FileTime()
    kernel = FileTime()
    user = FileTime()
    if not ctypes.windll.kernel32.GetSystemTimes(
        ctypes.byref(idle),
        ctypes.byref(kernel),
        ctypes.byref(user),
    ):
        return None
    return filetime_to_int(idle), filetime_to_int(kernel), filetime_to_int(user)


def cpu_load_percent(start, end):
    if not start or not end:
        return None
    idle_delta = int(end[0]) - int(start[0])
    kernel_delta = int(end[1]) - int(start[1])
    user_delta = int(end[2]) - int(start[2])
    total_delta = kernel_delta + user_delta
    if total_delta <= 0:
        return None
    load = (1.0 - (idle_delta / total_delta)) * 100.0
    return max(0.0, min(100.0, load))


def format_percent(value):
    return "none" if value is None else f"{value:.1f}"


def format_seconds(value):
    return "none" if value is None else f"{value:.2f}"


def config_path():
    return repo_root() / "voice_dictation_config.json"


def asr_model_dir():
    return repo_root() / "models" / "asr" / "gigaam-v3-ctc"


def default_punct_model_dir():
    return repo_root() / "models" / "openvino" / "RUPunct_big_fp16_static128"


DEVICE_CHOICES = ("CPU", "GPU", "NPU")
DEFAULT_ASR_MODEL = "gigaam-v3-ctc-onnx-int8"
OPENVINO_ASR_MODEL = "gigaam-v3-ctc-openvino-fp32"
OPENVINO_ASR_NNCF_INT8_MODEL = "gigaam-v3-ctc-openvino-nncf-int8-b400"
DEFAULT_PUNCT_MODEL = "rupunct-big-openvino-fp16-static128"
DEFAULT_ASR_BUCKET_FRAMES = (400, 800, 1000, 1600, 3200)
DEFAULT_ASR_WARMUP_BUCKETS = DEFAULT_ASR_BUCKET_FRAMES
DEFAULT_ASR_RETRY_BUCKETS = (1600, 3200)
DEFAULT_ASR_CHUNK_BUCKET = 800
DEFAULT_ASR_CHUNK_OVERLAP_MS = 350
DEFAULT_ASR_VAD_MAX_SPEECH_S = 7.5
DEFAULT_ASR_VAD_MIN_SILENCE_MS = 100
DEFAULT_ASR_VAD_SPEECH_PAD_MS = 300
DEFAULT_ASR_VAD_FIRST_PAD_MS = 500
DEFAULT_ASR_VAD_MIN_SEGMENT_MS = 0
DEFAULT_AUDIO_PRE_ROLL_MS = 350
ASR_PAD_MODES = {"zero", "silence", "edge", "min"}

ASR_MODEL_PROFILES = {
    DEFAULT_ASR_MODEL: {
        "label": "GigaAM v3 CTC (ONNX INT8)",
        "backend": "onnx_asr",
        "onnx_asr_name": "gigaam-v3-ctc",
        "quantization": "int8",
        "model_dir": asr_model_dir,
        "devices": ("CPU",),
        "default_device": "CPU",
    },
    OPENVINO_ASR_MODEL: {
        "label": "GigaAM v3 CTC (OpenVINO FP32)",
        "backend": "openvino_ctc",
        "model_file": "v3_ctc.onnx",
        "model_dir": asr_model_dir,
        "devices": ("CPU", "NPU"),
        "default_device": "NPU",
    },
    OPENVINO_ASR_NNCF_INT8_MODEL: {
        "label": "GigaAM v3 CTC (OpenVINO NNCF INT8 b400)",
        "backend": "openvino_ctc",
        "model_file": "../gigaam-v3-ctc-openvino-int8-calib96/v3_ctc_bucket400_nncf_int8.xml",
        "model_dir": asr_model_dir,
        "cache_key": "asr_gigaam_nncf_int8_calib96_b400",
        "devices": ("CPU", "NPU"),
        "default_device": "NPU",
    },
}

PUNCT_MODEL_PROFILES = {
    DEFAULT_PUNCT_MODEL: {
        "label": "RUPunct big (OpenVINO FP16 static 128)",
        "model_dir": default_punct_model_dir,
        "devices": ("CPU", "NPU"),
        "default_device": "NPU",
    },
}


def device_is_available(devices, device):
    target = str(device or "").upper()
    if not target:
        return False
    for item in devices:
        item = str(item or "").upper()
        if item == target or item.startswith(f"{target}."):
            return True
    return False


def normalize_model_id(profiles, value, default):
    return value if value in profiles else default


def model_profile(profiles, value, default):
    return profiles[normalize_model_id(profiles, value, default)]


def model_labels(profiles):
    return [profile["label"] for profile in profiles.values()]


def model_label(profiles, value, default):
    return model_profile(profiles, value, default)["label"]


def model_id_from_label(profiles, label, default):
    for model_id, profile in profiles.items():
        if profile["label"] == label:
            return model_id
    return default


def normalize_model_device(profiles, model_id, device):
    profile = model_profile(profiles, model_id, next(iter(profiles)))
    device = str(device or "").upper()
    if device in profile["devices"]:
        return device
    return profile.get("default_device") or profile["devices"][0]


def selected_openvino_devices(cfg):
    devices = set()
    asr_model = normalize_model_id(ASR_MODEL_PROFILES, cfg.get("asr_model"), DEFAULT_ASR_MODEL)
    asr_profile = model_profile(ASR_MODEL_PROFILES, asr_model, DEFAULT_ASR_MODEL)
    if asr_profile.get("backend") == "openvino_ctc":
        devices.add(normalize_model_device(ASR_MODEL_PROFILES, asr_model, cfg.get("asr_device")))

    if cfg.get("use_punctuation", True):
        punct_model = normalize_model_id(PUNCT_MODEL_PROFILES, cfg.get("punct_model"), DEFAULT_PUNCT_MODEL)
        devices.add(normalize_model_device(PUNCT_MODEL_PROFILES, punct_model, cfg.get("punct_device")))

    return sorted(device for device in devices if device)


def probe_openvino_hardware(cfg):
    info = {
        "available": False,
        "version": None,
        "devices": [],
        "device_names": {},
        "selected_devices": selected_openvino_devices(cfg),
        "warnings": [],
        "error": None,
    }

    try:
        import openvino as ov

        info["version"] = getattr(ov, "__version__", None)
        core = ov.Core()
        devices = list(core.available_devices)
        info["available"] = True
        info["devices"] = devices

        for device in devices:
            try:
                info["device_names"][device] = str(core.get_property(device, "FULL_DEVICE_NAME"))
            except Exception as exc:
                info["device_names"][device] = f"unavailable: {type(exc).__name__}"
    except Exception as exc:
        info["error"] = type(exc).__name__

    if info["available"]:
        for device in info["selected_devices"]:
            if not device_is_available(info["devices"], device):
                info["warnings"].append(f"Selected OpenVINO device {device} was not reported by OpenVINO.")
    elif info["selected_devices"]:
        info["warnings"].append("OpenVINO hardware probe failed while OpenVINO device profiles are selected.")

    return info


def log_openvino_hardware(info):
    if not info:
        return
    log_debug(
        "openvino hardware "
        f"available={info.get('available')} version={info.get('version')} "
        f"devices={','.join(info.get('devices') or []) or 'none'} "
        f"selected={','.join(info.get('selected_devices') or []) or 'none'} "
        f"warnings={';'.join(info.get('warnings') or []) or 'none'} "
        f"error={info.get('error') or 'none'}"
    )


def normalize_model_config(cfg):
    cfg["asr_model"] = normalize_model_id(ASR_MODEL_PROFILES, cfg.get("asr_model"), DEFAULT_ASR_MODEL)
    cfg["asr_device"] = normalize_model_device(ASR_MODEL_PROFILES, cfg["asr_model"], cfg.get("asr_device"))
    cfg["asr_pad_mode"] = normalize_asr_pad_mode(cfg.get("asr_pad_mode"))
    cfg["asr_bucket_frames"] = normalize_asr_bucket_frames(cfg.get("asr_bucket_frames"))
    cfg["asr_chunked"] = bool(cfg.get("asr_chunked", False))
    cfg["asr_chunk_bucket"] = normalize_asr_chunk_bucket(cfg.get("asr_chunk_bucket"))
    cfg["asr_chunk_overlap_ms"] = normalize_asr_chunk_overlap_ms(cfg.get("asr_chunk_overlap_ms"))
    cfg["asr_vad_segments"] = bool(cfg.get("asr_vad_segments", False))
    cfg["asr_vad_max_speech_s"] = normalize_float(
        cfg.get("asr_vad_max_speech_s"),
        DEFAULT_ASR_VAD_MAX_SPEECH_S,
        1.0,
        30.0,
    )
    cfg["asr_vad_min_silence_ms"] = normalize_int(
        cfg.get("asr_vad_min_silence_ms"),
        DEFAULT_ASR_VAD_MIN_SILENCE_MS,
        20,
        2000,
    )
    cfg["asr_vad_speech_pad_ms"] = normalize_int(
        cfg.get("asr_vad_speech_pad_ms"),
        DEFAULT_ASR_VAD_SPEECH_PAD_MS,
        0,
        1000,
    )
    cfg["asr_vad_first_pad_ms"] = normalize_int(
        cfg.get("asr_vad_first_pad_ms"),
        DEFAULT_ASR_VAD_FIRST_PAD_MS,
        0,
        2000,
    )
    cfg["asr_vad_min_segment_ms"] = normalize_int(
        cfg.get("asr_vad_min_segment_ms"),
        DEFAULT_ASR_VAD_MIN_SEGMENT_MS,
        0,
        5000,
    )
    cfg["asr_vad_stitch"] = bool(cfg.get("asr_vad_stitch", False))
    cfg["asr_vad_fuzzy_stitch"] = bool(cfg.get("asr_vad_fuzzy_stitch", False))
    cfg["punct_model"] = normalize_model_id(PUNCT_MODEL_PROFILES, cfg.get("punct_model"), DEFAULT_PUNCT_MODEL)
    cfg["punct_device"] = normalize_model_device(PUNCT_MODEL_PROFILES, cfg["punct_model"], cfg.get("punct_device"))
    cfg["audio_pre_roll_ms"] = normalize_int(
        cfg.get("audio_pre_roll_ms"),
        DEFAULT_AUDIO_PRE_ROLL_MS,
        0,
        2000,
    )
    cfg["warmup_models"] = bool(cfg.get("warmup_models", True))
    cfg["asr_warmup_buckets"] = normalize_asr_warmup_buckets(cfg.get("asr_warmup_buckets"))
    cfg["asr_retry_fragmented"] = bool(cfg.get("asr_retry_fragmented", True))
    cfg["asr_retry_buckets"] = normalize_asr_retry_buckets(cfg.get("asr_retry_buckets"))
    cfg["restore_clipboard_after_paste"] = bool(cfg.get("restore_clipboard_after_paste", True))
    cfg["overlay_shape"] = normalize_overlay_shape(cfg.get("overlay_shape"))
    return cfg


def normalize_overlay_shape(value):
    value = str(value or "rounded").strip().lower()
    return value if value in OVERLAY_SHAPES else "rounded"


def normalize_asr_pad_mode(value):
    value = str(value or "zero").strip().lower()
    return value if value in ASR_PAD_MODES else "zero"


def normalize_asr_warmup_buckets(value):
    return normalize_bucket_list(value, DEFAULT_ASR_WARMUP_BUCKETS)


def normalize_asr_bucket_frames(value):
    return normalize_bucket_list(value, DEFAULT_ASR_BUCKET_FRAMES)


def normalize_asr_retry_buckets(value):
    return normalize_bucket_list(value, DEFAULT_ASR_RETRY_BUCKETS)


def normalize_asr_chunk_bucket(value):
    try:
        bucket = int(value)
    except (TypeError, ValueError):
        bucket = DEFAULT_ASR_CHUNK_BUCKET
    return bucket if bucket > 0 else DEFAULT_ASR_CHUNK_BUCKET


def normalize_asr_chunk_overlap_ms(value):
    try:
        overlap_ms = int(value)
    except (TypeError, ValueError):
        overlap_ms = DEFAULT_ASR_CHUNK_OVERLAP_MS
    return max(0, min(1500, overlap_ms))


def normalize_int(value, default, min_value, max_value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = default
    return max(min_value, min(max_value, value))


def normalize_float(value, default, min_value, max_value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = default
    return max(min_value, min(max_value, value))


def normalize_bucket_list(value, default):
    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, (list, tuple)):
        raw_values = value
    else:
        raw_values = default

    buckets = []
    for raw_value in raw_values:
        try:
            bucket = int(raw_value)
        except (TypeError, ValueError):
            continue
        if bucket > 0 and bucket not in buckets:
            buckets.append(bucket)
    return buckets or list(default)


def active_asr_warmup_buckets(asr, cfg):
    if (
        (cfg.get("asr_chunked", False) and hasattr(asr, "recognize_chunked"))
        or (cfg.get("asr_vad_segments", False) and hasattr(asr, "recognize_segments_16k"))
    ):
        return [normalize_asr_chunk_bucket(cfg.get("asr_chunk_bucket"))]

    buckets = normalize_asr_warmup_buckets(cfg.get("asr_warmup_buckets"))
    if cfg.get("asr_retry_fragmented", True):
        buckets.extend(
            bucket
            for bucket in normalize_asr_retry_buckets(cfg.get("asr_retry_buckets"))
            if bucket not in buckets
        )
    active_buckets = getattr(asr, "bucket_frames", None)
    if not active_buckets:
        return buckets
    active_buckets = set(int(bucket) for bucket in active_buckets)
    active_buckets.update(normalize_asr_retry_buckets(cfg.get("asr_retry_buckets")))
    filtered = [bucket for bucket in buckets if bucket in active_buckets]
    return filtered or [bucket for bucket in DEFAULT_ASR_WARMUP_BUCKETS if bucket in active_buckets]


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
        "asr_model": DEFAULT_ASR_MODEL,
        "asr_device": "CPU",
        "asr_pad_mode": "zero",
        "asr_bucket_frames": list(DEFAULT_ASR_BUCKET_FRAMES),
        "asr_chunked": False,
        "asr_chunk_bucket": DEFAULT_ASR_CHUNK_BUCKET,
        "asr_chunk_overlap_ms": DEFAULT_ASR_CHUNK_OVERLAP_MS,
        "asr_vad_segments": False,
        "asr_vad_max_speech_s": DEFAULT_ASR_VAD_MAX_SPEECH_S,
        "asr_vad_min_silence_ms": DEFAULT_ASR_VAD_MIN_SILENCE_MS,
        "asr_vad_speech_pad_ms": DEFAULT_ASR_VAD_SPEECH_PAD_MS,
        "asr_vad_first_pad_ms": DEFAULT_ASR_VAD_FIRST_PAD_MS,
        "asr_vad_min_segment_ms": DEFAULT_ASR_VAD_MIN_SEGMENT_MS,
        "asr_vad_stitch": False,
        "asr_vad_fuzzy_stitch": False,
        "input_device_index": choose_default_device_index(),
        "sample_rate": 0,
        "channels": 1,
        "audio_pre_roll_ms": DEFAULT_AUDIO_PRE_ROLL_MS,
        "use_punctuation": True,
        "save_debug_audio": False,
        "warmup_models": True,
        "asr_warmup_buckets": list(DEFAULT_ASR_WARMUP_BUCKETS),
        "asr_retry_fragmented": True,
        "asr_retry_buckets": list(DEFAULT_ASR_RETRY_BUCKETS),
        "compare_asr": False,
        "punct_model": DEFAULT_PUNCT_MODEL,
        "punct_device": "NPU",
        "auto_paste": True,
        "restore_clipboard_after_paste": True,
        "use_context": True,
        "context_chars": 320,
        "append_space": True,
        "start_with_windows": False,
        "overlay_visible": True,
        "overlay_x": None,
        "overlay_y": None,
        "overlay_size": "medium",
        "overlay_shape": "rounded",
        "overlay_details": "full",
        "overlay_opacity": 1.0,
    }


def load_config():
    cfg = default_config()
    path = config_path()
    if path.exists():
        with path.open("r", encoding="utf-8-sig") as file:
            loaded = json.load(file)
        cfg.update(loaded)
    return normalize_model_config(cfg)


def save_config(cfg):
    path = config_path()
    with path.open("w", encoding="utf-8") as file:
        json.dump(cfg, file, ensure_ascii=False, indent=2)


def debug_dictation_dir():
    return repo_root() / "recordings" / "debug_dictation"


def save_debug_audio(audio, sample_rate):
    debug_dir = debug_dictation_dir()
    debug_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    milliseconds = int((time.time() % 1) * 1000)
    path = debug_dir / f"dictation_{timestamp}_{milliseconds:03d}.wav"
    sf.write(path, audio, int(sample_rate), subtype="PCM_16")
    return path


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


def asr_bucket_label(asr):
    bucket = getattr(asr, "last_bucket", None)
    return str(bucket) if bucket is not None else "none"


def asr_pad_mode_label(asr):
    return str(getattr(asr, "pad_mode", "none"))


def should_use_chunked_asr(asr, cfg):
    return bool(cfg.get("asr_chunked", False)) and hasattr(asr, "recognize_chunked")


def should_use_vad_asr(asr, vad, cfg):
    return (
        bool(cfg.get("asr_vad_segments", False))
        and vad is not None
        and hasattr(asr, "recognize_segments_16k")
        and hasattr(asr, "audio_16k")
    )


def vad_options(cfg):
    return {
        "max_speech_duration_s": normalize_float(
            cfg.get("asr_vad_max_speech_s"),
            DEFAULT_ASR_VAD_MAX_SPEECH_S,
            1.0,
            30.0,
        ),
        "min_silence_duration_ms": normalize_int(
            cfg.get("asr_vad_min_silence_ms"),
            DEFAULT_ASR_VAD_MIN_SILENCE_MS,
            20,
            2000,
        ),
        "speech_pad_ms": normalize_int(
            cfg.get("asr_vad_speech_pad_ms"),
            DEFAULT_ASR_VAD_SPEECH_PAD_MS,
            0,
            1000,
        ),
    }


def vad_segment_ranges(vad, audio16, cfg):
    waveforms = audio16[None, :]
    waveforms_len = np.array([len(audio16)], dtype=np.int64)
    audio_len = len(audio16)
    segments = []
    for start, end in next(vad.segment_batch(waveforms, waveforms_len, 16_000, **vad_options(cfg))):
        start = max(0, min(audio_len, int(start)))
        end = max(0, min(audio_len, int(end)))
        if end > start:
            segments.append((start, end))
    if segments:
        first_pad = int(normalize_int(
            cfg.get("asr_vad_first_pad_ms"),
            DEFAULT_ASR_VAD_FIRST_PAD_MS,
            0,
            2000,
        ) * 16)
        start, end = segments[0]
        segments[0] = (max(0, start - first_pad), end)
    min_segment_samples = normalize_int(
        cfg.get("asr_vad_min_segment_ms"),
        DEFAULT_ASR_VAD_MIN_SEGMENT_MS,
        0,
        5000,
    ) * 16
    if min_segment_samples:
        segments = [(start, end) for start, end in segments if end - start >= min_segment_samples]
    return segments


def log_vad_segments(segments):
    for index, (start, end) in enumerate(segments):
        log_debug(
            "asr vad segment "
            f"index={index} start={start / 16000:.2f}s end={end / 16000:.2f}s "
            f"duration={(end - start) / 16000:.2f}s samples={end - start}"
        )


def log_asr_chunks(asr):
    chunks = getattr(asr, "last_chunks", None) or []
    for chunk in chunks:
        log_debug(
            "asr chunk "
            f"index={chunk.get('index')} "
            f"start={chunk.get('start_sec', 0.0):.2f}s "
            f"end={chunk.get('end_sec', 0.0):.2f}s "
            f"frames={chunk.get('frames')} "
            f"bucket={chunk.get('bucket')} "
            f"text={chunk.get('text')!r}"
        )


def asr_fragmentation_score(text):
    tokens = re.findall(r"[A-Za-zА-Яа-яЁё]+", str(text or ""))
    short_run = 0
    max_short_run = 0
    single_count = 0
    short_count = 0
    for token in tokens:
        length = len(token)
        if length == 1:
            single_count += 1
        if length <= 2:
            short_count += 1
        if length <= 3:
            short_run += 1
            max_short_run = max(max_short_run, short_run)
        else:
            short_run = 0

    total = max(len(tokens), 1)
    score = max_short_run * 3.0 + single_count * 2.5 + (short_count / total) * 4.0
    return {
        "score": score,
        "tokens": len(tokens),
        "single_count": single_count,
        "short_count": short_count,
        "max_short_run": max_short_run,
    }


def should_retry_fragmented_asr(score):
    return score["tokens"] >= 8 and (
        score["max_short_run"] >= 6
        or (score["max_short_run"] >= 5 and score["single_count"] >= 4)
    )


def asr_score_is_better(candidate, best):
    if candidate["max_short_run"] != best["max_short_run"]:
        return candidate["max_short_run"] < best["max_short_run"]
    if candidate["single_count"] != best["single_count"]:
        return candidate["single_count"] < best["single_count"]
    return candidate["score"] < best["score"]


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


def text_ends_clause(text):
    return bool(re.search("[,;:\\u2014-]+[\"')\\]]*$", str(text or "").rstrip()))


def first_non_space(text):
    for char in str(text or ""):
        if not char.isspace():
            return char
    return ""


def last_non_space(text):
    for char in reversed(str(text or "")):
        if not char.isspace():
            return char
    return ""


def starts_with_joining_punctuation(text):
    return first_non_space(text) in set(",.;:!?)]}»”’%…")


def context_blocks_leading_space(context):
    return last_non_space(context) in set("([{«“‘/\\-")


def should_prepend_insert_space(context, inserted_text):
    context = str(context or "")
    inserted_text = str(inserted_text or "")
    if not context or not context.strip() or not inserted_text.strip():
        return False
    if context[-1].isspace() or inserted_text[0].isspace():
        return False
    if context_blocks_leading_space(context):
        return False
    if starts_with_joining_punctuation(inserted_text):
        return False
    return True


def should_append_insert_space(inserted_text):
    stripped = str(inserted_text or "").rstrip()
    if not stripped:
        return False
    return last_non_space(stripped) not in set("([{«“‘/\\-—")


def apply_insertion_spacing(inserted_text, context="", append_trailing_space=False):
    inserted_text = str(inserted_text or "").strip()
    if not inserted_text:
        return ""

    prefix = " " if should_prepend_insert_space(context, inserted_text) else ""
    suffix = " " if append_trailing_space and should_append_insert_space(inserted_text) else ""
    return f"{prefix}{inserted_text}{suffix}"


def lowercase_first_alpha(text):
    text = str(text or "")
    for index, char in enumerate(text):
        if char.isalpha():
            return f"{text[:index]}{char.lower()}{text[index + 1:]}"
    return text


def first_alpha_is_lower(text):
    for char in str(text or ""):
        if char.isalpha():
            return char.islower()
    return False


def token_is_all_caps_word(text):
    letters = [char for char in str(text or "") if char.isalpha()]
    return bool(letters) and all(char.isupper() for char in letters)


def align_inserted_tokens(raw_text, inserted_text):
    raw_tokens = str(raw_text or "").split()
    inserted_tokens = str(inserted_text or "").split()
    if not raw_tokens or len(inserted_tokens) < len(raw_tokens):
        return raw_tokens, inserted_tokens, 0
    return raw_tokens, inserted_tokens, len(inserted_tokens) - len(raw_tokens)


def adjust_inserted_casing(raw_text, inserted_text, context=""):
    raw_tokens, inserted_tokens, start_index = align_inserted_tokens(raw_text, inserted_text)
    if not raw_tokens or not inserted_tokens:
        return str(inserted_text or "")

    previous_text = str(context or "")
    for token in inserted_tokens[:start_index]:
        previous_text = f"{previous_text} {token}".strip()

    for index, raw_token in enumerate(raw_tokens):
        inserted_index = start_index + index
        if inserted_index >= len(inserted_tokens):
            break
        should_lower = (
            first_alpha_is_lower(raw_token)
            or (text_ends_clause(previous_text) and not token_is_all_caps_word(raw_token))
        )
        if should_lower and previous_text and not text_ends_sentence(previous_text):
            inserted_tokens[inserted_index] = lowercase_first_alpha(inserted_tokens[inserted_index])
        previous_text = f"{previous_text} {inserted_tokens[inserted_index]}".strip()

    return " ".join(inserted_tokens)


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
    return adjust_inserted_casing(raw_text, f"{prefix}{tail}", context)


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
                return ""

            selections = pattern.GetSelection()
            if not selections:
                log_debug(f"uia context skipped=no-selection type={control_type}")
                return ""

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
        self.compare_asr = None
        self.compare_asr_signature = None
        self.vad = None
        self.punct = None
        self.loaded = False
        self.loading = False
        self.recording = False
        self.transcribing = False
        self.stream = None
        self.stream_signature = None
        self.sample_rate = None
        self.pre_roll_blocks = deque()
        self.pre_roll_samples = 0
        self.recording_pre_roll_sec = 0.0
        self.audio_blocks = []
        self.audio_callback_count = 0
        self.audio_callback_statuses = []
        self.audio_first_callback_perf = None
        self.audio_last_callback_perf = None
        self.audio_max_callback_gap = 0.0
        self.recording_cpu_start = None
        self.recording_cpu_end = None
        self.recording_wall_start = None
        self.recording_wall_end = None
        self.recording_context = ""
        self.hardware_info = None
        self.lock = threading.RLock()
        self.compare_lock = threading.RLock()
        self.keyboard = keyboard.Controller()

    def update_config(self, cfg):
        cfg = normalize_model_config(cfg)
        reload_asr = False
        restart_audio = False
        with self.lock:
            old_cfg = self.cfg
            reload_asr = (
                old_cfg.get("asr_model") != cfg.get("asr_model")
                or old_cfg.get("asr_device") != cfg.get("asr_device")
                or old_cfg.get("asr_pad_mode") != cfg.get("asr_pad_mode")
                or old_cfg.get("asr_bucket_frames") != cfg.get("asr_bucket_frames")
                or old_cfg.get("asr_chunked") != cfg.get("asr_chunked")
                or old_cfg.get("asr_chunk_bucket") != cfg.get("asr_chunk_bucket")
                or old_cfg.get("asr_vad_segments") != cfg.get("asr_vad_segments")
                or old_cfg.get("asr_vad_max_speech_s") != cfg.get("asr_vad_max_speech_s")
                or old_cfg.get("asr_vad_min_silence_ms") != cfg.get("asr_vad_min_silence_ms")
                or old_cfg.get("asr_vad_speech_pad_ms") != cfg.get("asr_vad_speech_pad_ms")
                or old_cfg.get("asr_vad_first_pad_ms") != cfg.get("asr_vad_first_pad_ms")
                or old_cfg.get("asr_vad_min_segment_ms") != cfg.get("asr_vad_min_segment_ms")
                or old_cfg.get("asr_vad_stitch") != cfg.get("asr_vad_stitch")
                or old_cfg.get("asr_vad_fuzzy_stitch") != cfg.get("asr_vad_fuzzy_stitch")
            )
            restart_audio = (
                old_cfg.get("input_device_index") != cfg.get("input_device_index")
                or old_cfg.get("sample_rate") != cfg.get("sample_rate")
                or old_cfg.get("channels") != cfg.get("channels")
            )
            self.cfg = cfg
            if reload_asr:
                self.asr = None
                self.vad = None
                self.compare_asr = None
                self.compare_asr_signature = None
                self.loaded = False
            if (
                old_cfg.get("punct_model") != cfg.get("punct_model")
                or old_cfg.get("punct_device") != cfg.get("punct_device")
            ):
                self.punct = None
        if restart_audio:
            self.close_audio_stream()
            if self.loaded:
                self.ensure_audio_stream()
        if reload_asr:
            self.load_async()

    def set_status(self, status):
        self.status_callback(status)

    def load_async(self):
        if self.loading or self.loaded:
            return
        self.loading = True
        threading.Thread(target=self._load_models, daemon=True).start()

    def _load_asr_profile(self, model_id, device, status_callback=None, cfg=None):
        profile = model_profile(ASR_MODEL_PROFILES, model_id, DEFAULT_ASR_MODEL)
        if profile["backend"] == "openvino_ctc":
            ensure_asr_openvino_model(status_callback)
            from gigaam_openvino_asr import GigaamOpenVinoCtcAsr

            cfg = cfg or self.cfg
            return GigaamOpenVinoCtcAsr(
                profile["model_dir"](),
                device=device,
                model_filename=profile["model_file"],
                cache_dir=repo_root() / "models" / "openvino" / "cache" / profile.get("cache_key", "asr_gigaam"),
                bucket_frames=normalize_asr_bucket_frames(cfg.get("asr_bucket_frames")),
                pad_mode=normalize_asr_pad_mode(cfg.get("asr_pad_mode")),
            )

        ensure_asr_model(status_callback)
        return onnx_asr.load_model(
            profile["onnx_asr_name"],
            profile["model_dir"](),
            quantization=profile["quantization"],
        )

    def _compare_target(self, cfg):
        active_model = normalize_model_id(ASR_MODEL_PROFILES, cfg.get("asr_model"), DEFAULT_ASR_MODEL)
        if active_model == DEFAULT_ASR_MODEL:
            target_model = OPENVINO_ASR_MODEL
            target_device = normalize_model_device(ASR_MODEL_PROFILES, target_model, "NPU")
        else:
            target_model = DEFAULT_ASR_MODEL
            target_profile = model_profile(ASR_MODEL_PROFILES, target_model, DEFAULT_ASR_MODEL)
            target_device = target_profile["default_device"]
        return target_model, target_device

    def _get_compare_asr(self, model_id, device):
        signature = (model_id, device)
        with self.compare_lock:
            if self.compare_asr is None or self.compare_asr_signature != signature:
                start = time.perf_counter()
                self.compare_asr = self._load_asr_profile(model_id, device)
                self.compare_asr_signature = signature
                log_debug(
                    "asr compare load done "
                    f"model={model_id} device={device} seconds={time.perf_counter() - start:.3f}"
                )
            return self.compare_asr

    def _get_vad(self):
        with self.lock:
            if self.vad is not None:
                return self.vad

        start = time.perf_counter()
        vad = onnx_asr.load_vad("silero")
        log_debug(f"load asr vad done model=silero seconds={time.perf_counter() - start:.3f}")
        with self.lock:
            if self.vad is None:
                self.vad = vad
            return self.vad

    def _compare_asr_async(self, audio, sample_rate, duration, active_text, active_sec, cfg):
        if not cfg.get("compare_asr", False):
            return

        active_model = normalize_model_id(ASR_MODEL_PROFILES, cfg.get("asr_model"), DEFAULT_ASR_MODEL)
        active_device = normalize_model_device(ASR_MODEL_PROFILES, active_model, cfg.get("asr_device"))
        compare_model, compare_device = self._compare_target(cfg)
        if (compare_model, compare_device) == (active_model, active_device):
            return

        audio = np.array(audio, dtype=np.float32, copy=True)

        def run_compare():
            try:
                compare_asr = self._get_compare_asr(compare_model, compare_device)
                start = time.perf_counter()
                compare_result = compare_asr.recognize(audio, sample_rate=sample_rate)
                compare_text = result_to_text(compare_result).strip()
                compare_bucket = asr_bucket_label(compare_asr)
                compare_sec = time.perf_counter() - start
                log_debug(
                    "asr compare "
                    f"audio={duration:.2f}s "
                    f"active_model={active_model} active_device={active_device} active_sec={active_sec:.3f} "
                    f"compare_model={compare_model} compare_device={compare_device} "
                    f"compare_bucket={compare_bucket} compare_sec={compare_sec:.3f} "
                    f"active_raw={active_text!r} compare_raw={compare_text!r}"
                )
            except Exception as exc:
                log_debug(
                    "asr compare error "
                    f"compare_model={compare_model} compare_device={compare_device} type={type(exc).__name__}"
                )

        threading.Thread(target=run_compare, daemon=True).start()

    def _retry_fragmented_asr(self, audio, sample_rate, raw_text, raw_bucket, cfg):
        if not cfg.get("asr_retry_fragmented", True):
            return raw_text, raw_bucket, []
        if not hasattr(self.asr, "recognize_with_bucket"):
            return raw_text, raw_bucket, []

        best_text = raw_text
        best_bucket = raw_bucket
        best_score = asr_fragmentation_score(raw_text)
        if not should_retry_fragmented_asr(best_score):
            return raw_text, raw_bucket, []

        retry_results = [
            {
                "bucket": raw_bucket,
                "score": best_score,
                "selected": False,
                "text": raw_text,
            }
        ]
        for bucket in normalize_asr_retry_buckets(cfg.get("asr_retry_buckets")):
            if str(bucket) == str(raw_bucket):
                continue
            try:
                start = time.perf_counter()
                candidate_result = self.asr.recognize_with_bucket(audio, sample_rate=sample_rate, bucket=bucket)
                candidate_text = result_to_text(candidate_result).strip()
                candidate_bucket = asr_bucket_label(self.asr)
                candidate_score = asr_fragmentation_score(candidate_text)
                retry_results.append(
                    {
                        "bucket": candidate_bucket,
                        "score": candidate_score,
                        "seconds": time.perf_counter() - start,
                        "selected": False,
                        "text": candidate_text,
                    }
                )
                if candidate_text and asr_score_is_better(candidate_score, best_score):
                    best_text = candidate_text
                    best_bucket = candidate_bucket
                    best_score = candidate_score
            except Exception as exc:
                log_debug(f"asr retry error bucket={bucket} type={type(exc).__name__}")

        for result in retry_results:
            result["selected"] = str(result["bucket"]) == str(best_bucket) and result["text"] == best_text
            score = result["score"]
            log_debug(
                "asr retry candidate "
                f"bucket={result['bucket']} selected={result['selected']} "
                f"score={score['score']:.3f} max_short_run={score['max_short_run']} "
                f"single_count={score['single_count']} short_count={score['short_count']} "
                f"seconds={result.get('seconds', 0.0):.3f} "
                f"text={result['text']!r}"
            )
        return best_text, best_bucket, retry_results

    def _warmup_models(self, asr, punct, cfg):
        if not cfg.get("warmup_models", True):
            log_debug("warmup skipped disabled=True")
            return

        self.set_status("Warming models")
        if hasattr(asr, "warmup"):
            buckets = active_asr_warmup_buckets(asr, cfg)
            start = time.perf_counter()
            try:
                warmed = asr.warmup(buckets)
                log_debug(
                    "warmup asr done "
                    f"model={cfg.get('asr_model')} device={cfg.get('asr_device')} "
                    f"buckets={','.join(str(bucket) for bucket in warmed)} "
                    f"seconds={time.perf_counter() - start:.3f}"
                )
            except Exception as exc:
                log_debug(f"warmup asr error type={type(exc).__name__}")
        else:
            log_debug(
                "warmup asr skipped "
                f"model={cfg.get('asr_model')} device={cfg.get('asr_device')} reason=no-warmup-method"
            )

        if punct is not None:
            start = time.perf_counter()
            try:
                punct.restore("проверка прогрева модели")
                log_debug(
                    "warmup punct done "
                    f"model={cfg.get('punct_model')} device={cfg.get('punct_device')} "
                    f"seconds={time.perf_counter() - start:.3f}"
                )
            except Exception as exc:
                log_debug(f"warmup punct error type={type(exc).__name__}")

    def _load_models(self):
        try:
            load_start = time.perf_counter()
            log_debug("load start")
            cfg = dict(self.cfg)
            hardware_info = probe_openvino_hardware(cfg)
            log_openvino_hardware(hardware_info)
            with self.lock:
                self.hardware_info = hardware_info
            asr_profile = model_profile(ASR_MODEL_PROFILES, cfg.get("asr_model"), DEFAULT_ASR_MODEL)
            self.set_status("Loading ASR")
            asr_start = time.perf_counter()
            asr = self._load_asr_profile(
                cfg.get("asr_model"),
                cfg.get("asr_device", asr_profile["default_device"]),
                self.set_status,
                cfg,
            )
            log_debug(
                "load asr done "
                f"model={cfg.get('asr_model')} device={cfg.get('asr_device')} "
                f"seconds={time.perf_counter() - asr_start:.3f}"
            )

            punct = None
            if cfg.get("use_punctuation", True):
                punct_profile = model_profile(PUNCT_MODEL_PROFILES, cfg.get("punct_model"), DEFAULT_PUNCT_MODEL)
                self.set_status("Loading punct dependencies")
                log_debug("load punct import start")
                from rupunct_restore import RUPunctRestorer
                log_debug("load punct import done")

                self.set_status("Loading punct")
                log_debug("load punct ensure start")
                ensure_punct_model(self.set_status)
                log_debug("load punct ensure done")
                punct_start = time.perf_counter()
                punct = RUPunctRestorer(
                    punct_profile["model_dir"](),
                    cfg.get("punct_device", "NPU"),
                    cache_dir=repo_root() / "models" / "openvino" / "cache",
                )
                log_debug(
                    "load punct done "
                    f"model={cfg.get('punct_model')} device={cfg.get('punct_device')} "
                    f"seconds={time.perf_counter() - punct_start:.3f}"
                )

            self._warmup_models(asr, punct, cfg)

            with self.lock:
                self.asr = asr
                self.punct = punct
                self.loaded = True
                self.loading = False
            self.ensure_audio_stream()
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

    def audio_stream_signature(self):
        sample_rate = self.resolve_sample_rate()
        return (
            self.cfg.get("input_device_index"),
            int(self.cfg.get("channels") or 1),
            sample_rate,
        )

    def close_audio_stream(self):
        with self.lock:
            stream = self.stream
            self.stream = None
            self.stream_signature = None
            self.pre_roll_blocks.clear()
            self.pre_roll_samples = 0

        if stream:
            try:
                stream.stop()
                stream.close()
            except Exception as exc:
                log_debug(f"audio stream close error={type(exc).__name__}")

    def ensure_audio_stream(self):
        try:
            signature = self.audio_stream_signature()
        except Exception as exc:
            log_debug(f"audio stream signature error={type(exc).__name__}")
            self.set_status(f"Audio error: {type(exc).__name__}")
            return False

        with self.lock:
            if self.stream and self.stream_signature == signature:
                self.sample_rate = signature[2]
                return True
            old_stream = self.stream
            self.stream = None
            self.stream_signature = None
            self.pre_roll_blocks.clear()
            self.pre_roll_samples = 0

        if old_stream:
            try:
                old_stream.stop()
                old_stream.close()
            except Exception as exc:
                log_debug(f"audio stream restart close error={type(exc).__name__}")

        device_index, channels, sample_rate = signature
        try:
            stream = sd.InputStream(
                samplerate=sample_rate,
                channels=channels,
                dtype="float32",
                device=device_index,
                callback=self._audio_callback,
            )
            with self.lock:
                self.stream = stream
                self.stream_signature = signature
                self.sample_rate = sample_rate
                self.pre_roll_blocks.clear()
                self.pre_roll_samples = 0
            stream.start()
            log_debug(
                "audio stream ready "
                f"device={device_index} channels={channels} sample_rate={sample_rate} "
                f"pre_roll_ms={int(self.cfg.get('audio_pre_roll_ms') or 0)}"
            )
            return True
        except Exception as exc:
            with self.lock:
                if self.stream is locals().get("stream"):
                    self.stream = None
                    self.stream_signature = None
            log_debug(f"audio stream error={type(exc).__name__}")
            self.set_status(f"Audio error: {type(exc).__name__}")
            return False

    def append_pre_roll_block_locked(self, block):
        pre_roll_ms = int(self.cfg.get("audio_pre_roll_ms") or 0)
        max_samples = int((self.sample_rate or 0) * pre_roll_ms / 1000)
        if max_samples <= 0:
            self.pre_roll_blocks.clear()
            self.pre_roll_samples = 0
            return

        self.pre_roll_blocks.append(block)
        self.pre_roll_samples += len(block)
        while self.pre_roll_blocks and self.pre_roll_samples > max_samples:
            removed = self.pre_roll_blocks.popleft()
            self.pre_roll_samples -= len(removed)

    def pre_roll_snapshot_locked(self):
        blocks = [block.copy() for block in self.pre_roll_blocks]
        seconds = self.pre_roll_samples / self.sample_rate if self.sample_rate else 0.0
        return blocks, seconds

    def clear_pre_roll_locked(self):
        self.pre_roll_blocks.clear()
        self.pre_roll_samples = 0

    def start_recording(self):
        with self.lock:
            if self.recording or self.transcribing:
                return
            if not self.loaded:
                self.set_status("Still loading")
                self.load_async()
                return

        if not self.ensure_audio_stream():
            return

        with self.lock:
            if self.recording or self.transcribing:
                return
            pre_roll_blocks, pre_roll_sec = self.pre_roll_snapshot_locked()
            self.audio_blocks = pre_roll_blocks
            self.audio_callback_count = 0
            self.audio_callback_statuses = []
            self.audio_first_callback_perf = None
            self.audio_last_callback_perf = None
            self.audio_max_callback_gap = 0.0
            self.recording_pre_roll_sec = pre_roll_sec
            self.recording_cpu_start = system_cpu_times()
            self.recording_cpu_end = None
            self.recording_wall_start = time.perf_counter()
            self.recording_wall_end = None
            self.recording_context = ""
            self.recording = True
            self.set_status("Recording")

        log_debug(f"recording start pre_roll={pre_roll_sec:.3f}s blocks={len(pre_roll_blocks)}")
        context = self.context_before_cursor()
        if context:
            with self.lock:
                if self.recording:
                    self.recording_context = context

    def stop_recording(self):
        with self.lock:
            if not self.recording:
                return
            self.recording = False
            self.recording_cpu_end = system_cpu_times()
            self.recording_wall_end = time.perf_counter()
            self.clear_pre_roll_locked()

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
            self.recording = False
            self.audio_blocks = []
            self.recording_context = ""
            self.clear_pre_roll_locked()

        self.set_status("Ready" if self.loaded else "Starting")

    def _audio_callback(self, indata, frames, time_info, status):
        now = time.perf_counter()
        block = indata.copy()
        status_text = str(status) if status else ""
        with self.lock:
            self.append_pre_roll_block_locked(block)
            if self.recording:
                if self.audio_first_callback_perf is None:
                    self.audio_first_callback_perf = now
                if self.audio_last_callback_perf is not None:
                    self.audio_max_callback_gap = max(self.audio_max_callback_gap, now - self.audio_last_callback_perf)
                self.audio_last_callback_perf = now
                self.audio_callback_count += 1
                self.audio_blocks.append(block)
                if status_text and len(self.audio_callback_statuses) < 12:
                    self.audio_callback_statuses.append(status_text)
        if status:
            log_debug(f"audio callback status={status_text}")
            self.set_status(status_text)

    def _transcribe_recording(self):
        with self.lock:
            blocks = self.audio_blocks
            sample_rate = self.sample_rate
            cfg = dict(self.cfg)
            audio_callback_count = self.audio_callback_count
            audio_callback_statuses = list(self.audio_callback_statuses)
            audio_first_callback_perf = self.audio_first_callback_perf
            audio_max_callback_gap = self.audio_max_callback_gap
            recording_pre_roll_sec = self.recording_pre_roll_sec
            recording_cpu_start = self.recording_cpu_start
            recording_cpu_end = self.recording_cpu_end
            recording_wall_start = self.recording_wall_start
            recording_wall_end = self.recording_wall_end
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
            recording_cpu = cpu_load_percent(recording_cpu_start, recording_cpu_end)
            recording_wall = (
                recording_wall_end - recording_wall_start
                if recording_wall_start is not None and recording_wall_end is not None
                else None
            )
            first_callback_delay = (
                audio_first_callback_perf - recording_wall_start
                if audio_first_callback_perf is not None and recording_wall_start is not None
                else None
            )
            log_debug(
                "recording stats "
                f"audio={duration:.2f}s wall={format_seconds(recording_wall)}s "
                f"pre_roll={recording_pre_roll_sec:.2f}s "
                f"first_callback={format_seconds(first_callback_delay)}s "
                f"callbacks={audio_callback_count} max_callback_gap={audio_max_callback_gap:.3f}s "
                f"cpu_load={format_percent(recording_cpu)} "
                f"statuses={';'.join(audio_callback_statuses) if audio_callback_statuses else 'none'}"
            )
            if duration < 0.25:
                self.set_status("Too short")
                return

            debug_audio_path = None
            if cfg.get("save_debug_audio", False):
                try:
                    debug_audio_path = save_debug_audio(audio, sample_rate)
                    log_debug(f"debug audio saved path={debug_audio_path}")
                except Exception as exc:
                    log_debug(f"debug audio save error type={type(exc).__name__}")

            self.set_status("Transcribing")
            start = time.perf_counter()
            asr_cpu_start = system_cpu_times()
            vad = self._get_vad() if cfg.get("asr_vad_segments", False) else None
            asr_mode = "vad" if should_use_vad_asr(self.asr, vad, cfg) else (
                "chunked" if should_use_chunked_asr(self.asr, cfg) else "full"
            )
            if asr_mode == "vad":
                audio16 = self.asr.audio_16k(audio, sample_rate=sample_rate)
                segments = vad_segment_ranges(vad, audio16, cfg)
                log_vad_segments(segments)
                raw_result = self.asr.recognize_segments_16k(
                    audio16,
                    segments,
                    bucket=normalize_asr_chunk_bucket(cfg.get("asr_chunk_bucket")),
                    stitch=bool(cfg.get("asr_vad_stitch", False)),
                    fuzzy_stitch=bool(cfg.get("asr_vad_fuzzy_stitch", False)),
                )
                log_asr_chunks(self.asr)
            elif asr_mode == "chunked":
                raw_result = self.asr.recognize_chunked(
                    audio,
                    sample_rate=sample_rate,
                    bucket=normalize_asr_chunk_bucket(cfg.get("asr_chunk_bucket")),
                    overlap_ms=normalize_asr_chunk_overlap_ms(cfg.get("asr_chunk_overlap_ms")),
                )
                log_asr_chunks(self.asr)
            else:
                raw_result = self.asr.recognize(audio, sample_rate=sample_rate)
            raw_text = result_to_text(raw_result).strip()
            asr_bucket = asr_bucket_label(self.asr)
            asr_pad_mode = asr_pad_mode_label(self.asr)
            asr_sec = time.perf_counter() - start
            asr_cpu_load = cpu_load_percent(asr_cpu_start, system_cpu_times())
            if asr_mode == "full":
                raw_text, asr_bucket, retry_results = self._retry_fragmented_asr(
                    audio,
                    sample_rate,
                    raw_text,
                    asr_bucket,
                    cfg,
                )
                if retry_results:
                    asr_sec = time.perf_counter() - start
            self._compare_asr_async(audio, sample_rate, duration, raw_text, asr_sec, cfg)

            final_text = raw_text
            context = self.recording_context or ""
            punct_sec = 0.0
            if raw_text and cfg.get("use_punctuation", True):
                if self.punct is None:
                    punct_profile = model_profile(PUNCT_MODEL_PROFILES, cfg.get("punct_model"), DEFAULT_PUNCT_MODEL)
                    from rupunct_restore import RUPunctRestorer

                    ensure_punct_model(self.set_status)
                    self.punct = RUPunctRestorer(
                        punct_profile["model_dir"](),
                        cfg.get("punct_device", "NPU"),
                        cache_dir=repo_root() / "models" / "openvino" / "cache",
                    )
                start = time.perf_counter()
                context = context or self.context_before_cursor()
                if context:
                    if hasattr(self.punct, "restore_inserted"):
                        final_text = self.punct.restore_inserted(context, raw_text)
                        final_text = adjust_inserted_casing(raw_text, final_text, context)
                    else:
                        restored = self.punct.restore(f"{context} {raw_text}".strip())
                        final_text = inserted_text_from_context(raw_text, restored, context)
                else:
                    final_text = self.punct.restore(raw_text)
                    final_text = adjust_inserted_casing(raw_text, final_text)
                punct_sec = time.perf_counter() - start

            final_text = apply_insertion_spacing(
                final_text,
                context,
                append_trailing_space=bool(cfg.get("append_space", False)),
            )

            if final_text:
                log_debug(
                    "dictation result "
                    f"audio={duration:.2f}s asr_mode={asr_mode} asr_bucket={asr_bucket} asr_pad={asr_pad_mode} "
                    f"record_cpu={format_percent(recording_cpu)} asr_cpu={format_percent(asr_cpu_load)} "
                    f"callbacks={audio_callback_count} max_callback_gap={audio_max_callback_gap:.3f}s "
                    f"statuses={';'.join(audio_callback_statuses) if audio_callback_statuses else 'none'} "
                    f"audio_path={str(debug_audio_path) if debug_audio_path else 'none'} "
                    f"raw={raw_text!r} final={final_text!r} "
                    f"context_chars={len(context) if 'context' in locals() else 0}"
                )
                self.text_callback(raw_text, final_text, duration, asr_sec, punct_sec)
                if cfg.get("auto_paste", True):
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
        restore_clipboard = bool(self.cfg.get("restore_clipboard_after_paste", True))
        previous_clipboard = ""
        has_previous_clipboard = False
        if restore_clipboard:
            try:
                has_text_format = True
                if os.name == "nt":
                    try:
                        cf_unicode_text = 13
                        user32 = ctypes.WinDLL("user32", use_last_error=True)
                        has_text_format = bool(user32.IsClipboardFormatAvailable(cf_unicode_text))
                    except Exception as exc:
                        log_debug(f"clipboard format check failed error={type(exc).__name__}")
                if has_text_format:
                    previous_clipboard = pyperclip.paste()
                    has_previous_clipboard = True
            except Exception as exc:
                log_debug(f"clipboard read failed error={type(exc).__name__}")

        try:
            pyperclip.copy(text)
        except Exception as exc:
            log_debug(f"clipboard copy failed error={type(exc).__name__}")
            return False

        target_ready = None
        if self.focus_callback:
            target_ready = bool(self.focus_callback())
        time.sleep(0.12)

        def restore_previous_clipboard():
            if not restore_clipboard or not has_previous_clipboard:
                return
            time.sleep(0.25)
            try:
                pyperclip.copy(previous_clipboard)
                log_debug("clipboard restored=True")
            except Exception as exc:
                log_debug(f"clipboard restore failed error={type(exc).__name__}")

        sent = self.send_ctrl_v()
        log_debug(f"paste target_ready={target_ready} send_input={sent}")
        if sent:
            restore_previous_clipboard()
            return True

        try:
            self.keyboard.press(keyboard.Key.ctrl)
            self.keyboard.press("v")
            self.keyboard.release("v")
            self.keyboard.release(keyboard.Key.ctrl)
            log_debug("paste fallback=pynput")
            restore_previous_clipboard()
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
        self.root.configure(bg=OVERLAY_TRANSPARENT_COLOR)
        self.apply_overlay_transparency()
        self.apply_overlay_opacity()

        self.status_var = tk.StringVar(value="Loading models")
        self.current_status = "Loading models"
        self.current_display_status = "Loading models"
        self.last_text_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value=self.cfg.get("mode", "hold"))
        self.settings_i18n_widgets = []
        self.settings_i18n_choices = []
        self.settings_i18n_tabs = []
        self.progress_running = False
        self.overlay_progress_after_id = None
        self.overlay_progress_phase = 0
        self.overlay_button_text = self.t("button_dict")
        self.overlay_button_bg = "#2864d8"
        self.overlay_button_active_bg = "#1f55bd"
        self.overlay_button_bounds = (0, 0, 0, 0)
        self.overlay_window_size = (1, 1)
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
        self.mouse_pressed_on_button = False

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
        self.overlay_canvas = tk.Canvas(
            self.root,
            bg=OVERLAY_TRANSPARENT_COLOR,
            highlightthickness=0,
            borderwidth=0,
        )
        self.overlay_canvas.pack(fill="both", expand=True)

        self.apply_overlay_layout()

        for widget in (self.root, self.overlay_canvas):
            widget.bind("<Button-3>", self.show_menu)
            widget.bind("<ButtonPress-1>", self.on_overlay_press)
            widget.bind("<B1-Motion>", self.on_overlay_motion)
            widget.bind("<ButtonRelease-1>", self.on_overlay_release)

    def overlay_size_profile(self):
        profiles = {
            "small": {
                "padx": 8,
                "pady": 7,
                "button_width": 92,
                "button_height": 54,
                "button_font": ("Segoe UI", 10, "bold"),
                "status_font": ("Segoe UI", 8),
                "hotkey_font": ("Segoe UI", 7),
                "status_height": 18,
                "hotkey_height": 14,
                "progress_length": 84,
                "progress_height": 5,
                "gap": 5,
                "radius": 12,
            },
            "medium": {
                "padx": 10,
                "pady": 8,
                "button_width": 124,
                "button_height": 72,
                "button_font": ("Segoe UI", 13, "bold"),
                "status_font": ("Segoe UI", 10),
                "hotkey_font": ("Segoe UI", 9),
                "status_height": 22,
                "hotkey_height": 17,
                "progress_length": 108,
                "progress_height": 6,
                "gap": 6,
                "radius": 16,
            },
            "large": {
                "padx": 12,
                "pady": 10,
                "button_width": 160,
                "button_height": 88,
                "button_font": ("Segoe UI", 17, "bold"),
                "status_font": ("Segoe UI", 13),
                "hotkey_font": ("Segoe UI", 11),
                "status_height": 28,
                "hotkey_height": 20,
                "progress_length": 128,
                "progress_height": 7,
                "gap": 7,
                "radius": 20,
            },
        }
        return profiles.get(self.cfg.get("overlay_size", "medium"), profiles["medium"])

    def apply_overlay_transparency(self):
        try:
            self.root.wm_attributes("-transparentcolor", OVERLAY_TRANSPARENT_COLOR)
        except tk.TclError:
            pass

    def apply_overlay_opacity(self, opacity=None):
        opacity = clamp_overlay_opacity(self.cfg.get("overlay_opacity", 1.0) if opacity is None else opacity)
        try:
            self.root.attributes("-alpha", opacity)
        except tk.TclError:
            pass

    def overlay_shape_mode(self):
        return normalize_overlay_shape(self.cfg.get("overlay_shape"))

    def overlay_details_mode(self):
        value = self.cfg.get("overlay_details", "full")
        return value if value in {"button", "status", "full"} else "full"

    def apply_overlay_layout(self):
        profile = self.overlay_size_profile()
        details = self.overlay_details_mode()
        shape = self.overlay_shape_mode()
        button_width = int(profile["button_width"])
        button_height = int(profile["button_height"])
        if shape == "circle":
            button_width = button_height = max(button_width, button_height)

        if details == "button":
            width = button_width
            height = button_height
            button_x = 0
            button_y = 0
            content_width = button_width
        else:
            content_width = max(button_width, int(profile["progress_length"]))
            width = content_width + profile["padx"] * 2
            height = profile["pady"] * 2 + button_height
            height += profile["gap"] + profile["status_height"]
            if details == "full":
                height += profile["hotkey_height"]
            height += profile["gap"] + profile["progress_height"]
            button_x = profile["padx"] + (content_width - button_width) // 2
            button_y = profile["pady"]

        y = button_y + button_height
        status_y = None
        hotkey_y = None
        progress_y = None
        if details in {"status", "full"}:
            y += profile["gap"]
            status_y = y
            y += profile["status_height"]
        if details == "full":
            hotkey_y = y
            y += profile["hotkey_height"]
        if details in {"status", "full"}:
            y += profile["gap"]
            progress_y = y

        self.overlay_window_size = (int(width), int(height))
        self.overlay_button_bounds = (
            int(button_x),
            int(button_y),
            int(button_x + button_width),
            int(button_y + button_height),
        )
        self.overlay_geometry = {
            "profile": profile,
            "details": details,
            "shape": shape,
            "content_width": int(content_width),
            "status_y": status_y,
            "hotkey_y": hotkey_y,
            "progress_y": progress_y,
        }
        self.overlay_canvas.configure(width=int(width), height=int(height))
        self.root.geometry(f"{int(width)}x{int(height)}")
        self.draw_overlay()

    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, radius, fill, outline=None, width=1):
        radius = max(0, min(int(radius), int((x2 - x1) / 2), int((y2 - y1) / 2)))
        if radius <= 0:
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline or fill, width=width)
            return

        canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline="")
        canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=fill, outline="")
        canvas.create_oval(x1, y1, x1 + radius * 2, y1 + radius * 2, fill=fill, outline="")
        canvas.create_oval(x2 - radius * 2, y1, x2, y1 + radius * 2, fill=fill, outline="")
        canvas.create_oval(x2 - radius * 2, y2 - radius * 2, x2, y2, fill=fill, outline="")
        canvas.create_oval(x1, y2 - radius * 2, x1 + radius * 2, y2, fill=fill, outline="")
        if outline:
            canvas.create_arc(x1, y1, x1 + radius * 2, y1 + radius * 2, start=90, extent=90, style="arc", outline=outline, width=width)
            canvas.create_arc(x2 - radius * 2, y1, x2, y1 + radius * 2, start=0, extent=90, style="arc", outline=outline, width=width)
            canvas.create_arc(x2 - radius * 2, y2 - radius * 2, x2, y2, start=270, extent=90, style="arc", outline=outline, width=width)
            canvas.create_arc(x1, y2 - radius * 2, x1 + radius * 2, y2, start=180, extent=90, style="arc", outline=outline, width=width)
            canvas.create_line(x1 + radius, y1, x2 - radius, y1, fill=outline, width=width)
            canvas.create_line(x2, y1 + radius, x2, y2 - radius, fill=outline, width=width)
            canvas.create_line(x1 + radius, y2, x2 - radius, y2, fill=outline, width=width)
            canvas.create_line(x1, y1 + radius, x1, y2 - radius, fill=outline, width=width)

    def _draw_shape(self, canvas, x1, y1, x2, y2, shape, fill, outline=None, radius=16, width=1):
        if shape == "circle":
            canvas.create_oval(x1, y1, x2, y2, fill=fill, outline=outline or fill, width=width)
        elif shape == "rounded":
            self._draw_rounded_rect(canvas, x1, y1, x2, y2, radius, fill, outline=outline, width=width)
        else:
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline or fill, width=width)

    def fit_overlay_text(self, text, font, max_width):
        text = str(text)
        if max_width <= 0:
            return text
        try:
            measured_font = tkfont.Font(font=font)
        except tk.TclError:
            return text
        if measured_font.measure(text) <= max_width:
            return text

        suffix = "..."
        available = max(0, int(max_width) - measured_font.measure(suffix))
        clipped = text
        while clipped and measured_font.measure(clipped) > available:
            clipped = clipped[:-1]
        return f"{clipped.rstrip()}{suffix}" if clipped else suffix

    def draw_overlay(self):
        if not hasattr(self, "overlay_canvas"):
            return

        canvas = self.overlay_canvas
        canvas.delete("all")
        width, height = self.overlay_window_size
        geometry = getattr(self, "overlay_geometry", {})
        profile = geometry.get("profile", self.overlay_size_profile())
        details = geometry.get("details", self.overlay_details_mode())
        shape = geometry.get("shape", self.overlay_shape_mode())
        radius = int(profile.get("radius", 16))
        x1, y1, x2, y2 = self.overlay_button_bounds

        if details != "button":
            panel_shape = shape if shape != "circle" else "rounded"
            self._draw_shape(
                canvas,
                0,
                0,
                width,
                height,
                panel_shape,
                OVERLAY_PANEL_BG,
                outline=OVERLAY_PANEL_BORDER,
                radius=radius + 2,
            )

        self._draw_shape(
            canvas,
            x1,
            y1,
            x2,
            y2,
            shape,
            self.overlay_button_bg,
            outline=self.overlay_button_active_bg,
            radius=radius,
        )
        canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=self.overlay_button_text,
            fill="white",
            font=profile["button_font"],
            width=max(20, x2 - x1 - 12),
            justify="center",
        )

        content_width = int(geometry.get("content_width", x2 - x1))
        text_x = width / 2
        if details in {"status", "full"} and geometry.get("status_y") is not None:
            canvas.create_text(
                text_x,
                geometry["status_y"] + profile["status_height"] / 2,
                text=self.fit_overlay_text(self.status_var.get(), profile["status_font"], content_width),
                fill=OVERLAY_TEXT_FG,
                font=profile["status_font"],
                justify="center",
            )
        if details == "full" and geometry.get("hotkey_y") is not None:
            canvas.create_text(
                text_x,
                geometry["hotkey_y"] + profile["hotkey_height"] / 2,
                text=self.fit_overlay_text(str(self.cfg.get("dictation_hotkey", "f8")).upper(), profile["hotkey_font"], content_width),
                fill=OVERLAY_HINT_FG,
                font=profile["hotkey_font"],
                justify="center",
            )
        if details in {"status", "full"} and geometry.get("progress_y") is not None:
            progress_width = min(content_width, int(profile["progress_length"]))
            progress_x1 = (width - progress_width) / 2
            progress_y1 = geometry["progress_y"]
            progress_x2 = progress_x1 + progress_width
            progress_y2 = progress_y1 + profile["progress_height"]
            self._draw_rounded_rect(
                canvas,
                progress_x1,
                progress_y1,
                progress_x2,
                progress_y2,
                max(2, profile["progress_height"] // 2),
                "#303743",
            )
            if self.progress_running:
                span = max(18, int(progress_width * 0.34))
                travel = max(1, progress_width - span)
                offset = (self.overlay_progress_phase % 100) / 100 * travel
                self._draw_rounded_rect(
                    canvas,
                    progress_x1 + offset,
                    progress_y1,
                    progress_x1 + offset + span,
                    progress_y2,
                    max(2, profile["progress_height"] // 2),
                    "#75a7ff",
                )

    def _position_overlay(self):
        self.root.update_idletasks()
        width, height = getattr(
            self,
            "overlay_window_size",
            (self.root.winfo_reqwidth(), self.root.winfo_reqheight()),
        )
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
        self.root.geometry(f"{int(width)}x{int(height)}+{int(x)}+{int(y)}")
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
            self.settings_i18n_tabs = []
            return

        self.settings_window.title(f"{APP_NAME} {self.t('settings_title')}")
        for notebook, tab_id, key in self.settings_i18n_tabs:
            try:
                if notebook.winfo_exists():
                    notebook.tab(tab_id, text=self.t(key))
            except tk.TclError:
                pass
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
            "hardware": self.engine.hardware_info,
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
        self.draw_overlay()

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

    def set_overlay_button_state(self, text_key, bg, active_bg):
        self.overlay_button_text = self.t(text_key)
        self.overlay_button_bg = bg
        self.overlay_button_active_bg = active_bg
        self.draw_overlay()

    def set_overlay_progress_running(self, running):
        running = bool(running)
        if running == self.progress_running:
            return
        self.progress_running = running
        if running:
            self.advance_overlay_progress()
        else:
            if self.overlay_progress_after_id is not None:
                try:
                    self.root.after_cancel(self.overlay_progress_after_id)
                except tk.TclError:
                    pass
                self.overlay_progress_after_id = None
            self.draw_overlay()

    def advance_overlay_progress(self):
        self.overlay_progress_after_id = None
        if not self.progress_running:
            return
        self.overlay_progress_phase = (self.overlay_progress_phase + 7) % 100
        self.draw_overlay()
        self.overlay_progress_after_id = self.root.after(80, self.advance_overlay_progress)

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
        self.set_overlay_progress_running(show_progress)

        if status == "Recording":
            self.set_overlay_button_state("button_record", "#b83030", "#982727")
        elif status == "Loading ASR":
            self.set_overlay_button_state("button_asr", "#81612b", "#6d5124")
        elif status == "Loading punct":
            self.set_overlay_button_state("button_punct", "#81612b", "#6d5124")
        elif status == "Transcribing":
            self.set_overlay_button_state("button_text", "#81612b", "#6d5124")
        elif busy:
            self.set_overlay_button_state("button_busy", "#81612b", "#6d5124")
        elif status == "Pasted":
            self.set_overlay_button_state("button_ok", "#267d45", "#206b3b")
        elif status == "Copied":
            self.set_overlay_button_state("button_copy", "#2b7281", "#245f6c")
        elif status.startswith("Copied - paste"):
            self.set_overlay_button_state("button_paste", "#b85528", "#98441f")
        elif status in {"No audio", "Too short", "No speech"}:
            self.set_overlay_button_state("button_empty", "#5f6773", "#505762")
        elif status.startswith("Error") or status.startswith("Load error") or status in {
            "Bad hotkey",
            "Bad overlay key",
            "Hotkey conflict",
            "Startup error",
        }:
            self.set_overlay_button_state("button_error", "#9f3030", "#832929")
        else:
            self.set_overlay_button_state("button_dict", "#2864d8", "#1f55bd")

    def on_overlay_press(self, event):
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        self.overlay_start_x = self.root.winfo_x()
        self.overlay_start_y = self.root.winfo_y()
        self.dragging_overlay = False
        self.mouse_pressed_on_button = self.event_inside_overlay_button(event)
        self.mouse_recording_active = False

        if self.mouse_pressed_on_button and self.cfg.get("mode", "hold") == "hold":
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
        elif self.mouse_pressed_on_button:
            mode = self.cfg.get("mode", "hold")
            if mode == "hold" and self.mouse_recording_active:
                self.engine.stop_recording()
            elif mode == "toggle":
                self.engine.toggle_recording()

        self.dragging_overlay = False
        self.mouse_recording_active = False
        self.mouse_pressed_on_button = False

    def event_inside_overlay_button(self, event):
        x1, y1, x2, y2 = self.overlay_button_bounds
        return x1 <= int(event.x) <= x2 and y1 <= int(event.y) <= y2

    def move_overlay(self, x, y):
        x, y = self.clamp_overlay_position(x, y)
        width, height = getattr(self, "overlay_window_size", (self.root.winfo_width(), self.root.winfo_height()))
        self.root.geometry(f"{int(width)}x{int(height)}+{x}+{y}")
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
        self.apply_overlay_transparency()
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
        self.settings_i18n_tabs = []
        win.title(f"{APP_NAME} {self.t('settings_title')}")
        win.attributes("-topmost", True)
        win.resizable(True, True)
        win.configure(padx=24, pady=20)
        win.minsize(900, 560)
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)

        settings_font = ("Segoe UI", 12)
        settings_small_font = ("Segoe UI", 10)
        settings_style = ttk.Style(win)
        settings_style.configure("TLabel", font=settings_font)
        settings_style.configure("TCheckbutton", font=settings_font, padding=(0, 4))
        settings_style.configure("TButton", font=settings_font, padding=(12, 6))
        settings_style.configure("Settings.TLabelframe", padding=(16, 12))
        settings_style.configure("Settings.TLabelframe.Label", font=("Segoe UI", 12, "bold"))
        win.option_add("*TCombobox*Listbox.font", settings_font)

        mode = tk.StringVar(value=self.choice_label("mode", self.cfg.get("mode", "hold")))
        ui_language = tk.StringVar(value=UI_LANGUAGE_NAMES[normalize_ui_language(self.cfg.get("ui_language", "en"))])
        asr_model = tk.StringVar(value=model_label(ASR_MODEL_PROFILES, self.cfg.get("asr_model"), DEFAULT_ASR_MODEL))
        asr_device = tk.StringVar(
            value=normalize_model_device(ASR_MODEL_PROFILES, self.cfg.get("asr_model"), self.cfg.get("asr_device"))
        )
        punct_model = tk.StringVar(
            value=model_label(PUNCT_MODEL_PROFILES, self.cfg.get("punct_model"), DEFAULT_PUNCT_MODEL)
        )
        punct_device = tk.StringVar(
            value=normalize_model_device(
                PUNCT_MODEL_PROFILES,
                self.cfg.get("punct_model"),
                self.cfg.get("punct_device"),
            )
        )
        dict_hotkey = tk.StringVar(value=self.cfg.get("dictation_hotkey", "f8"))
        overlay_hotkey = tk.StringVar(value=self.cfg.get("overlay_hotkey", "ctrl+alt+shift+d"))
        overlay_size = tk.StringVar(value=self.choice_label("overlay_size", self.cfg.get("overlay_size", "medium")))
        overlay_shape = tk.StringVar(value=self.choice_label("overlay_shape", self.cfg.get("overlay_shape", "rounded")))
        overlay_details = tk.StringVar(value=self.choice_label("overlay_details", self.cfg.get("overlay_details", "full")))
        overlay_opacity = tk.DoubleVar(value=clamp_overlay_opacity(self.cfg.get("overlay_opacity", 1.0)) * 100)
        overlay_opacity_label = tk.StringVar()
        sample_rate = tk.StringVar(value=str(self.cfg.get("sample_rate", 0)))
        use_punctuation = tk.BooleanVar(value=bool(self.cfg.get("use_punctuation", True)))
        warmup_models = tk.BooleanVar(value=bool(self.cfg.get("warmup_models", True)))
        compare_asr = tk.BooleanVar(value=bool(self.cfg.get("compare_asr", False)))
        auto_paste = tk.BooleanVar(value=bool(self.cfg.get("auto_paste", True)))
        restore_clipboard = tk.BooleanVar(value=bool(self.cfg.get("restore_clipboard_after_paste", True)))
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

        def remember_tab(notebook, tab_id, key):
            self.settings_i18n_tabs.append((notebook, tab_id, key))
            return tab_id

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
                self.settings_i18n_tabs = []

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
            asr_model,
            asr_device,
            punct_model,
            punct_device,
            dict_hotkey,
            overlay_hotkey,
            overlay_size,
            overlay_shape,
            overlay_details,
            overlay_opacity,
            selected_device,
            sample_rate,
            use_punctuation,
            warmup_models,
            compare_asr,
            auto_paste,
            restore_clipboard,
            use_context,
            append_space,
            start_with_windows,
        ):
            variable.trace_add("write", mark_dirty)

        def update_opacity_label(*_):
            overlay_opacity_label.set(f"{int(round(overlay_opacity.get()))}%")

        overlay_opacity.trace_add("write", update_opacity_label)
        update_opacity_label()

        def create_device_selector(parent, model_var, device_var, profiles, default_model):
            frame = ttk.Frame(parent)
            buttons = {}
            state = {"model_id": None}
            for column, device in enumerate(DEVICE_CHOICES):
                button = ttk.Radiobutton(frame, text=device, value=device, variable=device_var)
                button.grid(row=0, column=column, sticky="w", padx=(0, 18))
                buttons[device] = button

            def refresh_devices(*_):
                model_id = model_id_from_label(profiles, model_var.get(), default_model)
                profile = model_profile(profiles, model_id, default_model)
                supported = set(profile["devices"])
                if state["model_id"] is not None and state["model_id"] != model_id:
                    device_var.set(profile.get("default_device") or profile["devices"][0])
                elif device_var.get() not in supported:
                    device_var.set(normalize_model_device(profiles, model_id, device_var.get()))
                state["model_id"] = model_id
                for device, button in buttons.items():
                    button.configure(state="normal" if device in supported else "disabled")

            model_var.trace_add("write", refresh_devices)
            refresh_devices()
            return frame

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
                "asr_model": model_id_from_label(ASR_MODEL_PROFILES, asr_model.get(), DEFAULT_ASR_MODEL),
                "asr_device": normalize_model_device(
                    ASR_MODEL_PROFILES,
                    model_id_from_label(ASR_MODEL_PROFILES, asr_model.get(), DEFAULT_ASR_MODEL),
                    asr_device.get(),
                ),
                "punct_model": model_id_from_label(PUNCT_MODEL_PROFILES, punct_model.get(), DEFAULT_PUNCT_MODEL),
                "punct_device": normalize_model_device(
                    PUNCT_MODEL_PROFILES,
                    model_id_from_label(PUNCT_MODEL_PROFILES, punct_model.get(), DEFAULT_PUNCT_MODEL),
                    punct_device.get(),
                ),
                "dictation_hotkey": dict_hotkey.get(),
                "overlay_hotkey": overlay_hotkey.get(),
                "overlay_size": self.choice_value("overlay_size", overlay_size.get(), "medium"),
                "overlay_shape": self.choice_value("overlay_shape", overlay_shape.get(), "rounded"),
                "overlay_details": self.choice_value("overlay_details", overlay_details.get(), "full"),
                "overlay_opacity": clamp_overlay_opacity(overlay_opacity.get() / 100),
                "input_device_index": int(selected_device.get().split(":", 1)[0]) if selected_device.get() else None,
                "sample_rate": sample_rate_value,
                "use_punctuation": bool(use_punctuation.get()),
                "warmup_models": bool(warmup_models.get()),
                "asr_bucket_frames": normalize_asr_bucket_frames(self.cfg.get("asr_bucket_frames")),
                "asr_warmup_buckets": normalize_asr_warmup_buckets(self.cfg.get("asr_warmup_buckets")),
                "compare_asr": bool(compare_asr.get()),
                "auto_paste": bool(auto_paste.get()),
                "restore_clipboard_after_paste": bool(restore_clipboard.get()),
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

        settings_notebook = ttk.Notebook(win)
        settings_notebook.grid(row=0, column=0, sticky="nsew")

        def settings_section(key):
            frame = ttk.Frame(settings_notebook, padding=(18, 16))
            frame.columnconfigure(1, weight=1)
            settings_notebook.add(frame, text=self.t(key))
            remember_tab(settings_notebook, frame, key)
            return frame

        general_section = settings_section("settings_section_general")
        row = 0
        i18n_label(general_section, "mode").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        mode_combo = ttk.Combobox(
            general_section,
            textvariable=mode,
            values=self.choice_labels("mode"),
            state="readonly",
            width=32,
            font=settings_font,
        )
        remember_choice(mode_combo, mode, "mode", "hold").grid(row=row, column=1, sticky="ew", pady=6)

        row += 1
        i18n_label(general_section, "ui_language").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        ttk.Combobox(
            general_section,
            textvariable=ui_language,
            values=list(UI_LANGUAGE_NAMES.values()),
            state="readonly",
            width=32,
            font=settings_font,
        ).grid(row=row, column=1, sticky="ew", pady=6)

        row += 1
        i18n_checkbutton(general_section, "start_with_windows", variable=start_with_windows).grid(
            row=row, column=1, sticky="w", pady=6
        )

        models_section = settings_section("settings_section_models")
        row = 0
        i18n_label(models_section, "asr_model").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        ttk.Combobox(
            models_section,
            textvariable=asr_model,
            values=model_labels(ASR_MODEL_PROFILES),
            state="readonly",
            width=42,
            font=settings_font,
        ).grid(row=row, column=1, sticky="ew", pady=6)

        row += 1
        i18n_label(models_section, "asr_device").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        create_device_selector(
            models_section,
            asr_model,
            asr_device,
            ASR_MODEL_PROFILES,
            DEFAULT_ASR_MODEL,
        ).grid(row=row, column=1, sticky="w", pady=6)

        row += 1
        i18n_checkbutton(models_section, "compare_asr", variable=compare_asr).grid(
            row=row, column=1, sticky="w", pady=6
        )

        row += 1
        i18n_checkbutton(models_section, "warmup_models", variable=warmup_models).grid(
            row=row, column=1, sticky="w", pady=6
        )

        row += 1
        i18n_label(models_section, "punct_model").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        ttk.Combobox(
            models_section,
            textvariable=punct_model,
            values=model_labels(PUNCT_MODEL_PROFILES),
            state="readonly",
            width=42,
            font=settings_font,
        ).grid(row=row, column=1, sticky="ew", pady=6)

        row += 1
        i18n_label(models_section, "punct_device").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        create_device_selector(
            models_section,
            punct_model,
            punct_device,
            PUNCT_MODEL_PROFILES,
            DEFAULT_PUNCT_MODEL,
        ).grid(row=row, column=1, sticky="w", pady=6)

        overlay_section = settings_section("settings_section_overlay")
        row = 0
        i18n_label(overlay_section, "overlay_size").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        overlay_size_combo = ttk.Combobox(
            overlay_section,
            textvariable=overlay_size,
            values=self.choice_labels("overlay_size"),
            state="readonly",
            width=32,
            font=settings_font,
        )
        remember_choice(overlay_size_combo, overlay_size, "overlay_size", "medium").grid(row=row, column=1, sticky="ew", pady=6)

        row += 1
        i18n_label(overlay_section, "overlay_shape").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        overlay_shape_combo = ttk.Combobox(
            overlay_section,
            textvariable=overlay_shape,
            values=self.choice_labels("overlay_shape"),
            state="readonly",
            width=32,
            font=settings_font,
        )
        remember_choice(overlay_shape_combo, overlay_shape, "overlay_shape", "rounded").grid(row=row, column=1, sticky="ew", pady=6)

        row += 1
        i18n_label(overlay_section, "overlay_details").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        overlay_details_combo = ttk.Combobox(
            overlay_section,
            textvariable=overlay_details,
            values=self.choice_labels("overlay_details"),
            state="readonly",
            width=32,
            font=settings_font,
        )
        remember_choice(overlay_details_combo, overlay_details, "overlay_details", "full").grid(row=row, column=1, sticky="ew", pady=6)

        row += 1
        i18n_label(overlay_section, "overlay_opacity").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        opacity_frame = ttk.Frame(overlay_section)
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

        hotkey_section = settings_section("settings_section_hotkeys")
        row = 0
        i18n_label(hotkey_section, "dictation_hotkey").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        dict_hotkey_frame = ttk.Frame(hotkey_section)
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
        i18n_label(hotkey_section, "overlay_hotkey").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        overlay_hotkey_frame = ttk.Frame(hotkey_section)
        overlay_hotkey_frame.grid(row=row, column=1, sticky="ew", pady=6)
        overlay_hotkey_frame.columnconfigure(0, weight=1)
        overlay_hotkey_entry = ttk.Entry(overlay_hotkey_frame, textvariable=overlay_hotkey, width=36, font=settings_font)
        overlay_hotkey_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        i18n_button(
            overlay_hotkey_frame,
            "assign",
            command=lambda: start_hotkey_capture(overlay_hotkey, overlay_hotkey_entry),
        ).grid(row=0, column=1, sticky="e")

        audio_section = settings_section("settings_section_audio")
        row = 0
        i18n_label(audio_section, "input_device").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        ttk.Combobox(audio_section, textvariable=selected_device, values=device_labels, state="readonly", width=72, font=settings_font).grid(
            row=row, column=1, sticky="ew", pady=6
        )

        row += 1
        i18n_label(audio_section, "sample_rate").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        ttk.Entry(audio_section, textvariable=sample_rate, width=36, font=settings_font).grid(row=row, column=1, sticky="w", pady=6)

        insertion_section = settings_section("settings_section_insertion")
        row = 0
        i18n_checkbutton(insertion_section, "use_punctuation", variable=use_punctuation).grid(
            row=row, column=1, sticky="w", pady=6
        )

        row += 1
        i18n_checkbutton(insertion_section, "paste_into_active_field", variable=auto_paste).grid(
            row=row, column=1, sticky="w", pady=6
        )

        row += 1
        i18n_checkbutton(insertion_section, "restore_clipboard_after_paste", variable=restore_clipboard).grid(
            row=row, column=1, sticky="w", pady=6
        )

        row += 1
        i18n_checkbutton(insertion_section, "use_context", variable=use_context).grid(
            row=row, column=1, sticky="w", pady=6
        )

        row += 1
        i18n_checkbutton(insertion_section, "append_trailing_space", variable=append_space).grid(
            row=row, column=1, sticky="w", pady=6
        )

        row += 1
        ttk.Label(insertion_section, textvariable=self.last_text_var, wraplength=760, foreground="#555", font=settings_small_font).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(12, 6)
        )

        buttons = ttk.Frame(win)
        buttons.grid(row=1, column=0, columnspan=2, sticky="e", pady=(14, 0))
        i18n_button(buttons, "hide_overlay", command=self.hide_overlay).pack(side="left", padx=(0, 10))
        i18n_button(buttons, "apply", command=lambda: apply_settings(close=False)).pack(side="left", padx=(0, 10))
        i18n_button(buttons, "save", command=lambda: apply_settings(close=True)).pack(side="left", padx=(0, 10))
        i18n_button(buttons, "cancel", command=close_settings).pack(side="left")
        dirty.set(False)

    def save_settings(self, win, values, close=True):
        values["ui_language"] = normalize_ui_language(values.get("ui_language", "en"))
        values["asr_model"] = normalize_model_id(ASR_MODEL_PROFILES, values.get("asr_model"), DEFAULT_ASR_MODEL)
        values["asr_device"] = normalize_model_device(ASR_MODEL_PROFILES, values["asr_model"], values.get("asr_device"))
        values["punct_model"] = normalize_model_id(
            PUNCT_MODEL_PROFILES,
            values.get("punct_model"),
            DEFAULT_PUNCT_MODEL,
        )
        values["punct_device"] = normalize_model_device(
            PUNCT_MODEL_PROFILES,
            values["punct_model"],
            values.get("punct_device"),
        )
        values["dictation_hotkey"] = values["dictation_hotkey"].lower().strip()
        values["overlay_hotkey"] = values["overlay_hotkey"].lower().strip()
        if values.get("overlay_size") not in {"small", "medium", "large"}:
            values["overlay_size"] = "medium"
        values["overlay_shape"] = normalize_overlay_shape(values.get("overlay_shape"))
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

        next_cfg = dict(self.cfg)
        next_cfg.update(values)
        self.cfg = normalize_model_config(next_cfg)
        save_config(self.cfg)
        self.hotkeys.update_config(self.cfg)
        self.engine.update_config(self.cfg)
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
        if self.overlay_progress_after_id is not None:
            try:
                self.root.after_cancel(self.overlay_progress_after_id)
            except tk.TclError:
                pass
            self.overlay_progress_after_id = None
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
        self.engine.close_audio_stream()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    app = VoiceDictationApp()
    app.run()


if __name__ == "__main__":
    main()
