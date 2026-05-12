import os
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MEDIA_ROOT: Path = Path(os.environ.get("MEDIA_ROOT", PROJECT_ROOT / "media"))
COMPUTE_DEVICE: str = os.getenv("COMPUTE_DEVICE", "cpu")
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")

# Logging configuration
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# LOG_FORMAT can be "json", "console", or unset (None).
# When unset, defaults based on RUN_MODE: production → json, everything else → console.
_raw_log_format = os.getenv("LOG_FORMAT")
if _raw_log_format in ("json", "console"):
    LOG_FORMAT: Literal["json", "console"] = _raw_log_format  # type: ignore[assignment]
else:
    _run_mode = os.getenv("RUN_MODE", "development")
    LOG_FORMAT = "json" if _run_mode == "production" else "console"
