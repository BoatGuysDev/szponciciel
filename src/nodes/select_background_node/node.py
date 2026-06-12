import random
from typing import TypedDict

from logging_config import get_logger
from nodes.state import PersonaRunState
from providers.stock_video_provider import VALID_CATEGORIES, StockVideoProvider
from providers.video_provider import VideoRequest
from utils.logging import describe_exception, log_exception

log = get_logger(__name__)


class SelectBackgroundResult(TypedDict, total=False):
    video_category: str
    background_video_path: str
    is_fatal_error: bool
    error_message: str | None


def select_background_node(state: PersonaRunState) -> SelectBackgroundResult:
    """Picks a random stock category and a clip from it for the background video."""

    if not VALID_CATEGORIES:
        return {
            "is_fatal_error": True,
            "error_message": "Background selection failed: no stock video categories configured.",
        }

    category = random.choice(sorted(VALID_CATEGORIES))
    try:
        path = StockVideoProvider().get_video(VideoRequest(category=category))
    except (FileNotFoundError, ValueError) as exc:
        log_exception(log, "background.selection_failed", exc, category=category)
        return {
            "is_fatal_error": True,
            "error_message": f"Background selection failed: {describe_exception(exc)}",
        }

    return {"video_category": category, "background_video_path": str(path)}
