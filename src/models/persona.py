from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Persona(SQLModel, table=True):
    __tablename__ = "personas"

    id: str = Field(primary_key=True)
    tiktok_account_id: str
    style: str | None = None
    tone: str | None = None
    language: str | None = None
    voice_speaker: str | None = None
    voice_speaker_wav: str | None = None  # path to .wav for voice cloning
    show_captions: bool = True
    real_news_ratio: float = 0.5
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
