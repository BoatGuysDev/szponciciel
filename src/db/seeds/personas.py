import os

from src.models import Persona

from ._utils import seed_records


def load() -> int:
    personas = [
        Persona(
            id="ground_truth_media",
            tiktok_account_id=os.environ["GROUND_TRUTH_MEDIA_ACCOUNT_ID"],
            style="neutral, factual",
            tone="informative",
            language="en",
            voice_speaker="Claribel Dervla",
            show_captions=True,
            real_news_ratio=1.0,
            is_active=True,
        ),
        # Add more personas here
    ]
    return seed_records(personas)
