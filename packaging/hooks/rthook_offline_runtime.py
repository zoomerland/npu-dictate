"""Apply the source runtime's telemetry policy before frozen-app imports."""

from offline_runtime import disable_optional_telemetry


disable_optional_telemetry()
