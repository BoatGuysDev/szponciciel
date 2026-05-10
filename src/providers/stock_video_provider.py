import random
from pathlib import Path

from config import MEDIA_ROOT
from providers.video_provider import VideoRequest

VALID_CATEGORIES: frozenset[str] = frozenset(
    {
        "fortnite",
        "galaxy",
        "minecraft",
        "satisfying",
        "subway_surfer",
        "temple_run",
        "trackmania",
        "ugc",
    }
)


class StockVideoProvider:
    def __init__(self, root: Path = MEDIA_ROOT) -> None:
        self.root = root

    def get_video(self, request: VideoRequest) -> Path:
        if request.category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category: {request.category!r}. "
                f"Valid categories: {sorted(VALID_CATEGORIES)}"
            )
        folder = self.root / request.category
        videos = list(folder.glob("*.mp4"))
        if not videos:
            raise FileNotFoundError(
                f"No .mp4 files found in {folder}. "
                f"Run scripts/download_videos.py to populate it."
            )
        return random.choice(videos)
