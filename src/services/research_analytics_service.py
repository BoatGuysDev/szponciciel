from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import TypedDict

from sqlalchemy import desc
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from db import get_engine
from logging_config import get_logger
from models import Persona, PersonaRun, Run, RunMetrics
from research_categories import NEWS_CATEGORY_IDS
from services.run_metrics_service import RunMetricsService
from utils.logging import log_exception

log = get_logger(__name__)


class PerformanceSummary(TypedDict):
    name: str
    videos: int
    score: float
    avg_views_per_hour: float
    avg_engagement_rate: float


class RecentWinner(TypedDict):
    topic: str
    category: str
    title: str
    score: float
    views: int | None
    engagement_rate: float | None


class ResearchAnalyticsSummary(TypedDict):
    top_categories: list[PerformanceSummary]
    top_topics: list[PerformanceSummary]
    underexplored_categories: list[str]
    recent_winners: list[RecentWinner]


class _MetricRecord(TypedDict):
    topic: str
    category: str
    title: str
    views: int | None
    engagement_rate: float | None
    views_per_hour: float
    shares_per_view: float
    saves_per_view: float
    score: float


class ResearchAnalyticsService:
    def __init__(self, *, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def refresh_from_zernio(self, *, days: int = 7) -> list[RunMetrics]:
        """Fetch latest Zernio analytics for active personas and persist snapshots."""

        with Session(self._engine) as session:
            personas = list(session.exec(select(Persona).where(Persona.is_active)).all())

        metrics_service = RunMetricsService(engine=self._engine)
        refreshed_rows: list[RunMetrics] = []
        for persona in personas:
            try:
                refreshed_rows.extend(metrics_service.generate_for_persona(persona, days=days))
            except Exception as exc:
                log_exception(log, "research_analytics.refresh_failed", exc, persona_id=persona.id)
                continue
        return refreshed_rows

    def refresh_and_summarize(
        self,
        *,
        refresh_days: int = 7,
        summary_days: int = 14,
        limit: int = 100,
    ) -> ResearchAnalyticsSummary:
        self.refresh_from_zernio(days=refresh_days)
        return self.summarize(days=summary_days, limit=limit)

    def summarize(self, *, days: int = 14, limit: int = 100) -> ResearchAnalyticsSummary:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with Session(self._engine) as session:
            metrics_rows = session.exec(
                select(RunMetrics)
                .where(RunMetrics.fetched_at >= cutoff.replace(tzinfo=None))
                .order_by(desc(RunMetrics.fetched_at))
                .limit(limit)
            ).all()

            run_ids = {row.run_id for row in metrics_rows}
            persona_run_ids = {row.persona_run_id for row in metrics_rows}
            runs = (
                {run.id: run for run in session.exec(select(Run).where(Run.id.in_(run_ids))).all()} if run_ids else {}
            )
            persona_runs = (
                {
                    persona_run.id: persona_run
                    for persona_run in session.exec(select(PersonaRun).where(PersonaRun.id.in_(persona_run_ids))).all()
                }
                if persona_run_ids
                else {}
            )

        records = _normalize_records(
            [
                _build_metric_record(row, runs.get(row.run_id), persona_runs.get(row.persona_run_id))
                for row in metrics_rows
            ]
        )
        records = [record for record in records if record["category"]]
        return {
            "top_categories": _aggregate(records, key="category", limit=5),
            "top_topics": _aggregate(records, key="topic", limit=10),
            "underexplored_categories": _underexplored_categories(records),
            "recent_winners": _recent_winners(records, limit=10),
        }


def _build_metric_record(row: RunMetrics, run: Run | None, persona_run: PersonaRun | None) -> _MetricRecord:
    views = row.views or 0
    hours = max(row.post_age_hours or 24.0, 1.0)
    topic = (run.topic if run else None) or (run.source_article_title if run else None) or ""
    category = (run.news_category if run else None) or ""

    return {
        "topic": topic,
        "category": category,
        "title": (run.source_article_title if run else None) or "",
        "views": row.views,
        "engagement_rate": row.engagement_rate,
        "views_per_hour": views / hours,
        "shares_per_view": _ratio(row.shares, views),
        "saves_per_view": _ratio(row.saves, views),
        "score": 0.0,
    }


def _normalize_records(records: list[_MetricRecord]) -> list[_MetricRecord]:
    if not records:
        return []

    max_views_per_hour = max((record["views_per_hour"] for record in records), default=0.0)
    max_engagement_rate = max((record["engagement_rate"] or 0.0 for record in records), default=0.0)
    max_shares_per_view = max((record["shares_per_view"] for record in records), default=0.0)
    max_saves_per_view = max((record["saves_per_view"] for record in records), default=0.0)

    normalized = []
    for record in records:
        score = (
            0.50 * _normalize(record["views_per_hour"], max_views_per_hour)
            + 0.25 * _normalize(record["engagement_rate"] or 0.0, max_engagement_rate)
            + 0.15 * _normalize(record["shares_per_view"], max_shares_per_view)
            + 0.10 * _normalize(record["saves_per_view"], max_saves_per_view)
        )
        normalized.append({**record, "score": round(score, 4)})
    return normalized


def _aggregate(records: list[_MetricRecord], *, key: str, limit: int) -> list[PerformanceSummary]:
    grouped: dict[str, list[_MetricRecord]] = defaultdict(list)
    for record in records:
        name = str(record[key]).strip()
        if name:
            grouped[name].append(record)

    summaries = [
        {
            "name": name,
            "videos": len(rows),
            "score": round(sum(row["score"] for row in rows) / len(rows), 4),
            "avg_views_per_hour": round(sum(row["views_per_hour"] for row in rows) / len(rows), 2),
            "avg_engagement_rate": round(
                sum(row["engagement_rate"] or 0.0 for row in rows) / len(rows),
                4,
            ),
        }
        for name, rows in grouped.items()
    ]
    return sorted(summaries, key=lambda item: item["score"], reverse=True)[:limit]


def _underexplored_categories(records: list[_MetricRecord]) -> list[str]:
    counts = defaultdict(int)
    for record in records:
        counts[record["category"]] += 1

    return sorted(category for category in NEWS_CATEGORY_IDS if counts[category] < 2)


def _recent_winners(records: list[_MetricRecord], *, limit: int) -> list[RecentWinner]:
    return [
        {
            "topic": record["topic"],
            "category": record["category"],
            "title": record["title"],
            "score": record["score"],
            "views": record["views"],
            "engagement_rate": record["engagement_rate"],
        }
        for record in sorted(records, key=lambda item: item["score"], reverse=True)[:limit]
    ]


def _ratio(numerator: int | None, denominator: int) -> float:
    if not numerator or denominator <= 0:
        return 0.0
    return numerator / denominator


def _normalize(value: float, maximum: float) -> float:
    if maximum <= 0:
        return 0.0
    return min(value / maximum, 1.0)
