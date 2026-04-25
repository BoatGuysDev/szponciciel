from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class VideoRequest:
    category: str
    narration: str | None = None
    tiktok_caption: str | None = None


class VideoProvider(Protocol):
    def get_video(self, request: VideoRequest) -> Path: ...
