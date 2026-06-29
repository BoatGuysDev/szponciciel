from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlmodel import Session, select

from db import get_engine, reset_db
from models import Persona, PersonaRun, Run, RunMetrics
from services.run_metrics_service import RunMetricsService


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
