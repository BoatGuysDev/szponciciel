import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class PersonaRun(SQLModel, table=True):
    __tablename__ = "persona_runs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    run_id: str = Field(foreign_key="runs.id")
    persona_id: str = Field(foreign_key="personas.id")
    status: str = "pending"  # "pending" | "running" | "completed" | "failed"
    content_type: str | None = None  # "real" | "fake"
    narration: str | None = None
    tiktok_caption: str | None = None
    audio_path: str | None = None
    video_category: str | None = None
    background_video_path: str | None = None
    output_video_path: str | None = None
    tiktok_post_id: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
