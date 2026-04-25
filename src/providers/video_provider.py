from pathlib import Path
from typing import Protocol


class VideoProvider(Protocol):
    def get_video(self, category: str) -> Path: ...
