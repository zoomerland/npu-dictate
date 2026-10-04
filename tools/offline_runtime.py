"""Disable optional OpenVINO telemetry inside this process, not system-wide."""

import sys


_TELEMETRY_PACKAGE = "openvino_telemetry"


def disable_optional_telemetry():
    """Select OpenVINO's built-in no-telemetry fallback before runtime imports."""
    for name, module in tuple(sys.modules.items()):
        if module is not None and (
            name == _TELEMETRY_PACKAGE or name.startswith(_TELEMETRY_PACKAGE + ".")
        ):
            raise RuntimeError(
                "Optional OpenVINO telemetry was imported before the offline runtime policy. "
                "Start NPU Dictate in a fresh process."
            )
    # None makes normal imports raise ModuleNotFoundError; OpenVINO handles this
    # optional dependency with its own telemetry_stub, without a consent-file write.
    sys.modules[_TELEMETRY_PACKAGE] = None
