from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlmodel import Session, select

from db import get_engine, reset_db
from models import Persona, PersonaRun, Run, RunMetrics
from services import RunMetricsService, generate_run_metrics_for_persona


@pytest.fixture(autouse=True)
def setup_db():
    reset_db()


def _seed_persona_run(*, zernio_post_id: str | None = "post-123", status: str = "completed") -> Persona:
    with Session(get_engine()) as session:
        persona = Persona(
            id="persona-1",
            tiktok_account_id="account-1",
            language="en",
            style="dramatic",
            tone="serious",
        )
        run = Run(status="completed")
        session.add(persona)
        session.add(run)
        session.commit()
        session.refresh(run)

        session.add(
            PersonaRun(
                run_id=run.id,
                persona_id=persona.id,
                status=status,
                zernio_post_id=zernio_post_id,
                completed_at=datetime(2026, 6, 29, 12, 0),
            )
        )
        session.commit()
        session.refresh(persona)
        return persona


def test_generate_run_metrics_for_persona_persists_snapshot():
    persona = _seed_persona_run()
    client = MagicMock()
    client.analytics.get_analytics.return_value = {
        "posts": [
            {
                "postId": "unmatched-post",
                "status": "published",
                "analytics": {"views": 999},
            },
            {
                "postId": "post-123",
                "status": "published",
                "publishedAt": "2026-06-29T10:00:00Z",
                "platformAnalytics": [
                    {
                        "platform": "tiktok",
                        "status": "published",
                        "platformPostId": "tiktok-native-1",
                        "accountId": "account-1",
                        "accountUsername": "news_account",
                        "platformPostUrl": "https://tiktok.example/video/1",
                        "syncStatus": "synced",
                        "analytics": {
                            "views": 1000,
                            "likes": 80,
                            "comments": 12,
                            "shares": 9,
                            "saves": 4,
                            "clicks": 3,
                            "impressions": 1200,
                            "reach": 950,
                            "engagementRate": 10.5,
                            "lastUpdated": "2026-06-29T12:00:00Z",
                        },
                    }
                ],
            },
        ],
        "pagination": {"page": 1, "limit": 100, "total": 2},
    }
    fetched_at = datetime(2026, 6, 29, 13, 0, tzinfo=timezone.utc)

    service = RunMetricsService(client=client)

    rows = service.generate_for_persona(persona, fetched_at=fetched_at)

    assert len(rows) == 1
    metrics = rows[0]
    assert metrics.persona_id == "persona-1"
    assert metrics.zernio_post_id == "post-123"
    assert metrics.platform == "tiktok"
    assert metrics.platform_post_id == "tiktok-native-1"
    assert metrics.account_id == "account-1"
    assert metrics.account_username == "news_account"
    assert metrics.views == 1000
    assert metrics.likes == 80
    assert metrics.comments == 12
    assert metrics.shares == 9
    assert metrics.saves == 4
    assert metrics.clicks == 3
    assert metrics.impressions == 1200
    assert metrics.reach == 950
    assert metrics.engagement_rate == 10.5
    assert metrics.post_age_hours == 3
    assert metrics.raw_payload["postId"] == "post-123"
    client.analytics.get_analytics.assert_called_once_with(
        platform="tiktok",
        account_id="account-1",
        from_date="2026-06-22",
        to_date="2026-06-29",
        limit=100,
        page=1,
    )

    with Session(get_engine()) as session:
        stored = session.exec(select(RunMetrics)).all()
        assert len(stored) == 1
        assert stored[0].views == 1000


def test_generate_run_metrics_for_persona_updates_existing_snapshot():
    persona = _seed_persona_run()
    client = MagicMock()
    client.analytics.get_analytics.return_value = {
        "posts": [
            {
                "postId": "post-123",
                "status": "published",
                "analytics": {
                    "views": 250,
                    "likes": 20,
                    "comments": 5,
                    "shares": 3,
                    "engagementRate": 11.2,
                },
            },
        ],
        "pagination": {"page": 1, "limit": 100, "total": 1},
    }
    fetched_at = datetime(2026, 6, 29, 13, 0, tzinfo=timezone.utc)

    service = RunMetricsService(client=client)
    first_rows = service.generate_for_persona(persona, fetched_at=fetched_at)

    client.analytics.get_analytics.return_value["posts"][0]["analytics"]["views"] = 500
    second_rows = service.generate_for_persona(persona, fetched_at=fetched_at)

    assert len(first_rows) == 1
    assert len(second_rows) == 1
    assert second_rows[0].id == first_rows[0].id
    assert second_rows[0].views == 500

    with Session(get_engine()) as session:
        stored = session.exec(select(RunMetrics)).all()
        assert len(stored) == 1
        assert stored[0].id == first_rows[0].id
        assert stored[0].views == 500


def test_generate_run_metrics_for_persona_skips_runs_without_zernio_post_id():
    persona = _seed_persona_run(zernio_post_id=None)
    client = MagicMock()

    service = RunMetricsService(client=client)

    rows = service.generate_for_persona(persona)

    assert rows == []
    client.analytics.get_analytics.assert_not_called()


def test_generate_run_metrics_for_persona_skips_incomplete_runs():
    persona = _seed_persona_run(status="failed")
    client = MagicMock()

    service = RunMetricsService(client=client)

    rows = service.generate_for_persona(persona)

    assert rows == []
    client.analytics.get_analytics.assert_not_called()


def test_generate_run_metrics_for_persona_export_smoke_test():
    persona = _seed_persona_run()
    client = MagicMock()
    client.analytics.get_analytics.return_value = {
        "posts": [{"postId": "post-123", "analytics": {"views": 7}}],
        "pagination": {"page": 1, "limit": 100, "total": 1},
    }

    rows = generate_run_metrics_for_persona(
        persona,
        client=client,
        fetched_at=datetime(2026, 6, 29, 13, 0, tzinfo=timezone.utc),
    )

    assert len(rows) == 1
    assert rows[0].views == 7


def test_generate_run_metrics_fetches_zernio_after_read_session_is_closed(monkeypatch):
    persona = _seed_persona_run()
    client = MagicMock()
    client.analytics.get_analytics.return_value = {
        "posts": [{"postId": "post-123", "analytics": {"views": 10}}],
        "pagination": {"page": 1, "limit": 100, "total": 1},
    }
    session_depth = 0
    fetch_session_depth = None
    service = RunMetricsService(client=client)

    original_iter = service._iter_analytics_posts

    def tracking_iter(*args, **kwargs):
        nonlocal fetch_session_depth
        fetch_session_depth = session_depth
        return original_iter(*args, **kwargs)

    class TrackingSession(Session):
        def __enter__(self):
            nonlocal session_depth
            session_depth += 1
            return super().__enter__()

        def __exit__(self, *args):
            nonlocal session_depth
            try:
                return super().__exit__(*args)
            finally:
                session_depth -= 1

    monkeypatch.setattr("services.run_metrics_service.Session", TrackingSession)
    monkeypatch.setattr(service, "_iter_analytics_posts", tracking_iter)

    rows = service.generate_for_persona(persona)

    assert len(rows) == 1
    assert fetch_session_depth == 0


def test_iter_analytics_posts_raises_when_page_limit_is_exceeded(monkeypatch):
    persona = _seed_persona_run()
    client = MagicMock()
    client.analytics.get_analytics.return_value = {
        "posts": [{"postId": "post-123"}],
        "pagination": {"hasNextPage": True},
    }
    service = RunMetricsService(client=client)
    monkeypatch.setattr("services.run_metrics_service.MAX_ANALYTICS_PAGES", 2)

    with pytest.raises(RuntimeError, match="exceeded 2 pages"):
        service._iter_analytics_posts(
            persona,
            from_date=datetime(2026, 6, 22, tzinfo=timezone.utc),
            to_date=datetime(2026, 6, 29, tzinfo=timezone.utc),
        )

    assert client.analytics.get_analytics.call_count == 2


def test_build_run_metrics_matches_snake_case_account_id_before_fallback():
    persona = Persona(
        id="persona-1",
        tiktok_account_id="account-1",
        language="en",
        style="dramatic",
        tone="serious",
    )
    persona_run = PersonaRun(run_id="run-1", persona_id=persona.id, zernio_post_id="post-123")
    payload = {
        "postId": "post-123",
        "platformAnalytics": [
            {
                "platform": "tiktok",
                "account_id": "other-account",
                "analytics": {"views": 999},
            },
            {
                "platform": "tiktok",
                "account_id": "account-1",
                "analytics": {"views": 123},
            },
        ],
    }

    metrics = RunMetricsService(client=MagicMock()).build_run_metrics(
        persona=persona,
        persona_run=persona_run,
        payload=payload,
        fetched_at=datetime(2026, 6, 29, 13, 0, tzinfo=timezone.utc),
    )

    assert metrics.account_id == "account-1"
    assert metrics.views == 123
