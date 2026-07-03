import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, Index
from sqlmodel import Field, SQLModel


class RunMetrics(SQLModel, table=True):
    __tablename__ = "run_metrics"
    __table_args__ = (Index("ux_run_metrics_persona_run_id", "persona_run_id", unique=True),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    run_id: str = Field(foreign_key="runs.id", index=True)
    persona_run_id: str = Field(foreign_key="persona_runs.id")
    persona_id: str = Field(foreign_key="personas.id", index=True)
    zernio_post_id: str = Field(index=True)
    platform: str = Field(default="tiktok", index=True)
    platform_post_id: str | None = Field(default=None, index=True)
    platform_post_url: str | None = None
    account_id: str | None = Field(default=None, index=True)
    account_username: str | None = None
    post_status: str | None = None
    sync_status: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    metrics_last_updated_at: datetime | None = None
    post_age_hours: float | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    clicks: int | None = None
    impressions: int | None = None
    reach: int | None = None
    engagement_rate: float | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
