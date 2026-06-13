from config import settings
from db.seeds._utils import seed_records
from models import Persona


def load() -> int:
    if not settings.ground_truth_media_account_id:
        raise RuntimeError("GROUND_TRUTH_MEDIA_ACCOUNT_ID is required to seed the ground_truth_media persona.")

    personas = [
        Persona(
            id="ground_truth_media",
            tiktok_account_id=settings.ground_truth_media_account_id,
            style="fictional news documentary",
            tone="confident, straight-faced",
            language="en",
            voice_speaker="Claribel Dervla",
            show_captions=True,
            fictional_news_ratio=0.9,
            is_active=True,
        ),
        # Add more personas here
    ]
    return seed_records(personas)
