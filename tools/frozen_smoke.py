"""Read back the offline policy in the import-only package smoke path."""
import sys


def offline_policy_receipt():
    package = "openvino_telemetry"
    if package not in sys.modules or sys.modules[package] is not None:
        raise RuntimeError("Optional telemetry import is not blocked")
    if any(name.startswith(package + ".") and module is not None
           for name, module in tuple(sys.modules.items())):
        raise RuntimeError("Optional telemetry submodule is loaded")

    from openvino.tools.ovc import telemetry_stub, telemetry_utils

    if telemetry_utils.tm is not telemetry_stub:
        raise RuntimeError("OpenVINO telemetry fallback is not active")
    return {
        "frozen": bool(getattr(sys, "frozen", False)),
        "optional_telemetry_blocked": True,
        "fallback": telemetry_stub.__name__,
    }
