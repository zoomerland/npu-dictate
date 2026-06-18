import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import sounddevice as sd

import voice_dictation_app as app


DEPENDENCIES = [
    "numpy",
    "onnx-asr",
    "openvino",
    "pillow",
    "pynput",
    "pyperclip",
    "pystray",
    "sounddevice",
    "soundfile",
    "scipy",
    "torch",
    "transformers",
    "uiautomation",
    "comtypes",
]


def status_item(status, name, detail="", data=None):
    return {
        "status": status,
        "name": name,
        "detail": str(detail or ""),
        "data": data,
    }


def dependency_versions():
    items = []
    for package in DEPENDENCIES:
        try:
            version = importlib.metadata.version(package)
            items.append(status_item("ok", package, version))
        except importlib.metadata.PackageNotFoundError:
            items.append(status_item("fail", package, "not installed"))
    return items


def model_path_checks():
    paths = {
        "asr_model_dir": app.asr_model_dir(),
        "asr_openvino_artifact_dir": app.repo_root() / "models" / "asr" / "gigaam-v3-ctc-openvino-int8-calib96",
        "punct_model_dir": app.default_punct_model_dir(),
        "openvino_cache_dir": app.repo_root() / "models" / "openvino" / "cache",
    }
    try:
        import model_setup

        paths["model_artifact_manifest"] = model_setup.artifact_manifest_cache_path()
    except Exception:
        pass
    items = []
    for name, path in paths.items():
        status = "ok" if path.exists() else "warn"
        items.append(status_item(status, name, str(path), {"exists": path.exists()}))
    return items


def config_summary():
    cfg = app.load_config()
    return {
        "path": str(app.config_path()),
        "exists": app.config_path().exists(),
        "ui_language": cfg.get("ui_language"),
        "mode": cfg.get("mode"),
        "dictation_hotkey": cfg.get("dictation_hotkey"),
        "overlay_hotkey": cfg.get("overlay_hotkey"),
        "asr_model": cfg.get("asr_model"),
        "asr_device": cfg.get("asr_device"),
        "punct_model": cfg.get("punct_model"),
        "punct_device": cfg.get("punct_device"),
        "use_punctuation": cfg.get("use_punctuation"),
        "auto_paste": cfg.get("auto_paste"),
        "restore_clipboard_after_paste": cfg.get("restore_clipboard_after_paste"),
        "use_context": cfg.get("use_context"),
        "append_space": cfg.get("append_space"),
        "audio_pre_roll_ms": cfg.get("audio_pre_roll_ms"),
        "compare_asr": cfg.get("compare_asr"),
    }


def config_checks(summary):
    items = []
    if summary["exists"]:
        items.append(status_item("ok", "config file", summary["path"]))
    else:
        items.append(status_item("warn", "config file", f"missing, defaults will be used: {summary['path']}"))

    asr_profile = app.ASR_MODEL_PROFILES.get(summary["asr_model"])
    if asr_profile and summary["asr_device"] in asr_profile["devices"]:
        items.append(status_item("ok", "ASR profile", f"{summary['asr_model']} on {summary['asr_device']}"))
    else:
        items.append(status_item("fail", "ASR profile", f"{summary['asr_model']} on {summary['asr_device']}"))

    punct_profile = app.PUNCT_MODEL_PROFILES.get(summary["punct_model"])
    if not summary["use_punctuation"]:
        items.append(status_item("ok", "punctuation profile", "disabled"))
    elif punct_profile and summary["punct_device"] in punct_profile["devices"]:
        items.append(status_item("ok", "punctuation profile", f"{summary['punct_model']} on {summary['punct_device']}"))
    else:
        items.append(status_item("fail", "punctuation profile", f"{summary['punct_model']} on {summary['punct_device']}"))
    return items


def audio_diagnostics():
    try:
        devices = []
        for device in app.input_devices():
            item = dict(device)
            item["name"] = " ".join(str(item.get("name", "")).split())
            item["hostapi"] = " ".join(str(item.get("hostapi", "")).split())
            devices.append(item)
        default_input = sd.default.device[0] if sd.default.device else None
        return {
            "status": "ok" if devices else "warn",
            "default_input": default_input,
            "input_devices": devices,
            "count": len(devices),
            "error": None,
        }
    except Exception as exc:
        return {
            "status": "fail",
            "default_input": None,
            "input_devices": [],
            "count": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }


def recent_log(lines):
    path = app.repo_root() / "voice_dictation.log"
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "tail": [],
        }
    try:
        tail = path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except OSError as exc:
        tail = [f"log read error: {type(exc).__name__}: {exc}"]
    return {
        "path": str(path),
        "exists": True,
        "tail": tail,
    }


def build_report(log_lines):
    cfg = config_summary()
    hardware = app.probe_openvino_hardware(app.load_config())
    audio = audio_diagnostics()
    report = {
        "app": app.APP_NAME,
        "python": sys.version,
        "platform": platform.platform(),
        "repo_root": str(app.repo_root()),
        "config": cfg,
        "checks": {
            "dependencies": dependency_versions(),
            "config": config_checks(cfg),
            "models": model_path_checks(),
        },
        "openvino": hardware,
        "audio": audio,
        "log": recent_log(log_lines),
    }
    return report


def iter_status_items(report):
    for section in report["checks"].values():
        yield from section

    audio = report["audio"]
    if audio["status"] == "ok":
        yield status_item("ok", "audio input devices", f"{audio['count']} found")
    elif audio["status"] == "warn":
        yield status_item("warn", "audio input devices", "none found")
    else:
        yield status_item("fail", "audio input devices", audio["error"])

    openvino = report["openvino"]
    if openvino["available"]:
        yield status_item("ok", "OpenVINO devices", ",".join(openvino["devices"]))
    else:
        yield status_item("fail", "OpenVINO probe", openvino.get("error") or "unavailable")
    for warning in openvino.get("warnings") or []:
        yield status_item("warn", "OpenVINO warning", warning)


def summary_counts(report):
    counts = {"ok": 0, "warn": 0, "fail": 0}
    for item in iter_status_items(report):
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return counts


def print_section(title):
    print()
    print(title)
    print("-" * len(title))


def print_items(items):
    for item in items:
        detail = f" - {item['detail']}" if item["detail"] else ""
        print(f"[{item['status'].upper()}] {item['name']}{detail}")


def print_human(report):
    print(f"{report['app']} doctor")
    print(f"Python: {report['python'].splitlines()[0]}")
    print(f"Platform: {report['platform']}")
    print(f"Repo: {report['repo_root']}")

    cfg = report["config"]
    print_section("Config")
    print(f"Path: {cfg['path']} (exists={cfg['exists']})")
    print(f"Mode: {cfg['mode']}, dictation hotkey: {cfg['dictation_hotkey']}, overlay hotkey: {cfg['overlay_hotkey']}")
    print(f"ASR: {cfg['asr_model']} on {cfg['asr_device']}")
    print(f"Punctuation: {cfg['punct_model']} on {cfg['punct_device']} (enabled={cfg['use_punctuation']})")
    print(f"Paste: auto={cfg['auto_paste']}, restore_clipboard={cfg['restore_clipboard_after_paste']}")
    print(f"Context: use_context={cfg['use_context']}, append_space={cfg['append_space']}, pre_roll_ms={cfg['audio_pre_roll_ms']}")

    print_section("Dependencies")
    print_items(report["checks"]["dependencies"])

    print_section("Models")
    print_items(report["checks"]["models"])

    print_section("OpenVINO")
    hardware = report["openvino"]
    print(f"Available: {hardware['available']}")
    print(f"Version: {hardware['version']}")
    print(f"Devices: {', '.join(hardware['devices']) if hardware['devices'] else 'none'}")
    for device, name in hardware["device_names"].items():
        print(f"  {device}: {name}")
    print(f"Selected OpenVINO devices: {', '.join(hardware['selected_devices']) or 'none'}")
    for warning in hardware["warnings"]:
        print(f"[WARN] {warning}")
    if hardware["error"]:
        print(f"[FAIL] {hardware['error']}")

    print_section("Audio")
    audio = report["audio"]
    print(f"Status: {audio['status']}")
    print(f"Default input index: {audio['default_input']}")
    if audio["error"]:
        print(f"[FAIL] {audio['error']}")
    for device in audio["input_devices"]:
        marker = "*" if device["index"] == audio["default_input"] else " "
        print(
            f"{marker} {device['index']}: {device['name']} "
            f"[{device['hostapi']}, {device['channels']} ch, {device['sample_rate']} Hz]"
        )

    print_section("Config Checks")
    print_items(report["checks"]["config"])

    print_section("Recent Log")
    log = report["log"]
    print(f"Path: {log['path']} (exists={log['exists']})")
    for line in log["tail"]:
        print(line)

    counts = summary_counts(report)
    print_section("Summary")
    print(f"OK={counts['ok']} WARN={counts['warn']} FAIL={counts['fail']}")


def main():
    parser = argparse.ArgumentParser(description="Print NPU Dictate environment diagnostics.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 when any FAIL item is present.")
    parser.add_argument("--log-lines", type=int, default=25, help="Number of recent log lines to include.")
    args = parser.parse_args()

    report = build_report(max(0, args.log_lines))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)

    counts = summary_counts(report)
    if args.strict and counts["fail"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
