import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    status: str  # "running" | "completed" | "failed"
    source_article_url: str | None = None
    source_article_title: str | None = None
    base_script: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
