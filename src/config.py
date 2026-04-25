import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MEDIA_ROOT: Path = Path(os.environ.get("MEDIA_ROOT", PROJECT_ROOT / "media"))
