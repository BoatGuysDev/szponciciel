from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, select
from zernio import Zernio

from config import settings
from db import get_engine
from models import Persona, PersonaRun, RunMetrics


class RunMetricsService:
    def __init__(self, *, client: Zernio | None = None, engine: Engine | None = None) -> None:
        self._client = client
        self._engine = engine or get_engine()

    @property
    def client(self) -> Zernio:
        if self._client is None:
            self._client = Zernio(api_key=settings.zernio_api_key)
        return self._client

    def generate_for_persona(
        self,
        persona: Persona,
        *,
        fetched_at: datetime | None = None,
        days: int = 7,
    ) -> list[RunMetrics]:
        """Fetch Zernio analytics and persist snapshots matching this persona's posts."""

        snapshot_time = _ensure_aware_utc(fetched_at or datetime.now(timezone.utc))
        cutoff_time = snapshot_time - timedelta(days=days)

        with Session(self._engine) as session:
            persona_runs = session.exec(
                select(PersonaRun)
                .where(PersonaRun.persona_id == persona.id)
                .where(PersonaRun.status == "completed")
                .where(PersonaRun.zernio_post_id.is_not(None))
                .where(PersonaRun.completed_at >= cutoff_time.replace(tzinfo=None))
            ).all()
            persona_runs_by_post_id = {persona_run.zernio_post_id: persona_run for persona_run in persona_runs}
            if not persona_runs_by_post_id:
                return []

            metrics_rows: list[RunMetrics] = []
            for post_payload in self._iter_analytics_posts(persona, from_date=cutoff_time, to_date=snapshot_time):
                zernio_post_id = _zernio_post_id(post_payload)
                persona_run = persona_runs_by_post_id.get(zernio_post_id)
                if persona_run is None:
                    continue

                fetched_metrics = self.build_run_metrics(
                    persona=persona,
                    persona_run=persona_run,
                    payload=post_payload,
                    fetched_at=snapshot_time,
                )
                metrics = self._upsert_run_metrics(session, fetched_metrics)
                session.add(metrics)
                metrics_rows.append(metrics)

            session.commit()
            for metrics in metrics_rows:
                session.refresh(metrics)
            return metrics_rows

    def _iter_analytics_posts(
        self,
        persona: Persona,
        *,
        from_date: datetime,
        to_date: datetime,
    ) -> list[dict[str, Any]]:
        posts: list[dict[str, Any]] = []
        page = 1
        while True:
            payload = self.client.analytics.get_analytics(
                platform="tiktok",
                account_id=persona.tiktok_account_id,
                from_date=from_date.date().isoformat(),
                to_date=to_date.date().isoformat(),
                limit=100,
                page=page,
            )

            page_posts = _analytics_posts(payload)
            posts.extend(page_posts)
            if not _has_next_page(payload, page, len(page_posts)):
                return posts
            page += 1

    def _upsert_run_metrics(self, session: Session, fetched_metrics: RunMetrics) -> RunMetrics:
        existing = session.exec(
            select(RunMetrics).where(RunMetrics.persona_run_id == fetched_metrics.persona_run_id)
        ).first()
        if existing is None:
            return fetched_metrics

        existing.run_id = fetched_metrics.run_id
        existing.persona_id = fetched_metrics.persona_id
        existing.zernio_post_id = fetched_metrics.zernio_post_id
        existing.platform = fetched_metrics.platform
        existing.platform_post_id = fetched_metrics.platform_post_id
        existing.platform_post_url = fetched_metrics.platform_post_url
        existing.account_id = fetched_metrics.account_id
        existing.account_username = fetched_metrics.account_username
        existing.post_status = fetched_metrics.post_status
        existing.sync_status = fetched_metrics.sync_status
        existing.published_at = fetched_metrics.published_at
        existing.fetched_at = fetched_metrics.fetched_at
        existing.metrics_last_updated_at = fetched_metrics.metrics_last_updated_at
        existing.post_age_hours = fetched_metrics.post_age_hours
        existing.views = fetched_metrics.views
        existing.likes = fetched_metrics.likes
        existing.comments = fetched_metrics.comments
        existing.shares = fetched_metrics.shares
        existing.saves = fetched_metrics.saves
        existing.clicks = fetched_metrics.clicks
        existing.impressions = fetched_metrics.impressions
        existing.reach = fetched_metrics.reach
        existing.engagement_rate = fetched_metrics.engagement_rate
        existing.raw_payload = fetched_metrics.raw_payload
        return existing

    def build_run_metrics(
        self,
        *,
        persona: Persona,
        persona_run: PersonaRun,
        payload: dict[str, Any],
        fetched_at: datetime,
    ) -> RunMetrics:
        post_payload = _find_post_payload(payload, persona_run.zernio_post_id)
        platform_payload = _find_platform_payload(post_payload, persona)
        analytics_payload = _dict_value(platform_payload, "analytics") or _dict_value(post_payload, "analytics") or {}

        published_at = _parse_datetime(post_payload.get("publishedAt") or post_payload.get("published_at"))
        metrics_last_updated_at = _parse_datetime(
            analytics_payload.get("lastUpdated") or analytics_payload.get("last_updated")
        )
        normalized_fetched_at = _ensure_aware_utc(fetched_at)

        return RunMetrics(
            run_id=persona_run.run_id,
            persona_run_id=persona_run.id,
            persona_id=persona.id,
            zernio_post_id=persona_run.zernio_post_id,
            platform=str(platform_payload.get("platform") or post_payload.get("platform") or "tiktok"),
            platform_post_id=platform_payload.get("platformPostId") or platform_payload.get("platform_post_id"),
            platform_post_url=str(platform_payload.get("platformPostUrl") or post_payload.get("platformPostUrl") or "")
            or None,
            account_id=platform_payload.get("accountId")
            or platform_payload.get("account_id")
            or persona.tiktok_account_id,
            account_username=platform_payload.get("accountUsername") or platform_payload.get("account_username"),
            post_status=platform_payload.get("status") or post_payload.get("status"),
            sync_status=platform_payload.get("syncStatus") or post_payload.get("syncStatus"),
            published_at=published_at,
            fetched_at=normalized_fetched_at,
            metrics_last_updated_at=metrics_last_updated_at,
            post_age_hours=_post_age_hours(published_at, normalized_fetched_at),
            views=_int_value(analytics_payload, "views"),
            likes=_int_value(analytics_payload, "likes"),
            comments=_int_value(analytics_payload, "comments"),
            shares=_int_value(analytics_payload, "shares"),
            saves=_int_value(analytics_payload, "saves"),
            clicks=_int_value(analytics_payload, "clicks"),
            impressions=_int_value(analytics_payload, "impressions"),
            reach=_int_value(analytics_payload, "reach"),
            engagement_rate=_float_value(analytics_payload, "engagementRate", "engagement_rate"),
            raw_payload=payload,
        )


def generate_run_metrics_for_persona(
    persona: Persona,
    *,
    client: Zernio | None = None,
    fetched_at: datetime | None = None,
    days: int = 7,
) -> list[RunMetrics]:
    return RunMetricsService(client=client).generate_for_persona(persona, fetched_at=fetched_at, days=days)


def _find_post_payload(payload: dict[str, Any], zernio_post_id: str | None) -> dict[str, Any]:
    if isinstance(payload.get("post"), dict):
        return payload["post"]

    posts = payload.get("posts")
    if isinstance(posts, list):
        for post in posts:
            if isinstance(post, dict) and _matches_zernio_post_id(post, zernio_post_id):
                return post
        for post in posts:
            if isinstance(post, dict):
                return post

    return payload


def _analytics_posts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    posts = payload.get("posts")
    if isinstance(posts, list):
        return [post for post in posts if isinstance(post, dict)]

    if _zernio_post_id(payload):
        return [payload]

    return []


def _has_next_page(payload: dict[str, Any], page: int, post_count: int) -> bool:
    pagination = payload.get("pagination")
    if not isinstance(pagination, dict):
        return False

    total_pages = pagination.get("totalPages") or pagination.get("total_pages")
    if total_pages is not None:
        return page < int(total_pages)

    has_next = pagination.get("hasNextPage")
    if has_next is not None:
        return bool(has_next)

    limit = pagination.get("limit")
    total = pagination.get("total")
    if limit is not None and total is not None:
        return page * int(limit) < int(total)

    return post_count > 0 and bool(pagination.get("nextPage"))


def _zernio_post_id(post: dict[str, Any]) -> str | None:
    value = (
        post.get("_id")
        or post.get("id")
        or post.get("postId")
        or post.get("post_id")
        or post.get("latePostId")
        or post.get("late_post_id")
    )
    return str(value) if value else None


def _matches_zernio_post_id(post: dict[str, Any], zernio_post_id: str | None) -> bool:
    if not zernio_post_id:
        return False
    return _zernio_post_id(post) == zernio_post_id


def _find_platform_payload(post_payload: dict[str, Any], persona: Persona) -> dict[str, Any]:
    platform_entries = post_payload.get("platformAnalytics") or post_payload.get("platforms")
    if not isinstance(platform_entries, list):
        return post_payload

    for entry in platform_entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("platform") == "tiktok" and entry.get("accountId") == persona.tiktok_account_id:
            return entry

    for entry in platform_entries:
        if isinstance(entry, dict) and entry.get("platform") == "tiktok":
            return entry

    return post_payload


def _dict_value(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = payload.get(key)
    return value if isinstance(value, dict) else None


def _int_value(payload: dict[str, Any], *keys: str) -> int | None:
    value = _first_present(payload, *keys)
    if value is None:
        return None
    return int(value)


def _float_value(payload: dict[str, Any], *keys: str) -> float | None:
    value = _first_present(payload, *keys)
    if value is None:
        return None
    return float(value)


def _first_present(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_aware_utc(value)
    if not isinstance(value, str):
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        return _ensure_aware_utc(datetime.fromisoformat(normalized))
    except ValueError:
        return None


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _post_age_hours(published_at: datetime | None, fetched_at: datetime) -> float | None:
    if published_at is None:
        return None
    return (fetched_at - published_at).total_seconds() / 3600
