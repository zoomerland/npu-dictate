import os
import sys
from pathlib import Path


APP_ROOT_ENV = "LOCAL_VOICE_DICTATION_APP_ROOT"
DATA_ROOT_ENV = "LOCAL_VOICE_DICTATION_DATA_ROOT"


def app_root():
    override = os.environ.get(APP_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def user_data_root():
    override = os.environ.get(DATA_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return app_root()


def bundled_resource_root():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parents[1]
