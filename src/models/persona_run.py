from datetime import datetime

from sqlmodel import Field, SQLModel


class PersonaRun(SQLModel, table=True):
    __tablename__ = "persona_runs"

    id: str = Field(primary_key=True)  # UUID
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
    started_at: datetime | None = None
    completed_at: datetime | None = None
