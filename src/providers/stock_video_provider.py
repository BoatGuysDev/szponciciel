import random
from pathlib import Path

_MEDIA_ROOT = Path(__file__).resolve().parent.parent.parent / "media"

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
    def __init__(self, root: Path = _MEDIA_ROOT) -> None:
        self.root = root

    def get_video(self, category: str) -> Path:
        folder = self.root / category
        if not folder.exists():
            raise FileNotFoundError(
                f"Video category folder not found: {folder}. "
                f"Valid categories: {sorted(VALID_CATEGORIES)}"
            )
        videos = list(folder.glob("*.mp4"))
        if not videos:
            raise FileNotFoundError(
                f"No .mp4 files found in {folder}. "
                f"Run scripts/download_videos.py to populate it."
            )
        return random.choice(videos)
