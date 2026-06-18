import os
import sys
from pathlib import Path


APP_ROOT_ENV = "LOCAL_VOICE_DICTATION_APP_ROOT"


def app_root():
    override = os.environ.get(APP_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def bundled_resource_root():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parents[1]
