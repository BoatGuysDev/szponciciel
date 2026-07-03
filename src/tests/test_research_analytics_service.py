from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, select

from db import get_engine, reset_db
from models import Persona, PersonaRun, Run, RunMetrics
from services.research_analytics_service import ResearchAnalyticsService


@pytest.fixture(autouse=True)
def setup_db():
    reset_db()


def test_summarize_aggregates_run_metrics_by_topic_and_category():
    now = datetime.now(timezone.utc)
    with Session(get_engine()) as session:
        persona = Persona(id="p1", tiktok_account_id="account-1")
        ai_run = Run(
            status="completed",
            topic="AI agents",
            news_category="ai",
            research_query="AI agents news",
            source_article_title="AI agents replace office tasks",
        )
        world_run = Run(
            status="completed",
            topic="World diplomacy",
            news_category="world",
            research_query="world diplomacy news",
            source_article_title="Leaders meet for talks",
        )
        session.add(persona)
        session.add(ai_run)
        session.add(world_run)
        session.commit()
        session.refresh(ai_run)
        session.refresh(world_run)

        ai_persona_run = PersonaRun(
            run_id=ai_run.id,
            persona_id=persona.id,
            status="completed",
            zernio_post_id="post-ai",
            completed_at=now,
        )
        world_persona_run = PersonaRun(
            run_id=world_run.id,
            persona_id=persona.id,
            status="completed",
            zernio_post_id="post-world",
            completed_at=now,
        )
        session.add(ai_persona_run)
        session.add(world_persona_run)
        session.commit()
        session.refresh(ai_persona_run)
        session.refresh(world_persona_run)

        session.add(
            RunMetrics(
                run_id=ai_run.id,
                persona_run_id=ai_persona_run.id,
                persona_id=persona.id,
                zernio_post_id="post-ai",
                fetched_at=now,
                views=1000,
                shares=100,
                saves=40,
                engagement_rate=0.2,
                post_age_hours=2,
            )
        )
        session.add(
            RunMetrics(
                run_id=world_run.id,
                persona_run_id=world_persona_run.id,
                persona_id=persona.id,
                zernio_post_id="post-world",
                fetched_at=now,
                views=100,
                shares=2,
                saves=1,
                engagement_rate=0.03,
                post_age_hours=10,
            )
        )
        session.commit()

    summary = ResearchAnalyticsService().summarize()

    assert summary["top_categories"][0]["name"] == "ai"
    assert summary["top_topics"][0]["name"] == "AI agents"
    assert summary["recent_winners"][0]["title"] == "AI agents replace office tasks"
    assert "finance" in summary["underexplored_categories"]


def test_refresh_from_zernio_fetches_active_personas_only():
    with Session(get_engine()) as session:
        active = Persona(id="active", tiktok_account_id="account-active")
        inactive = Persona(id="inactive", tiktok_account_id="account-inactive", is_active=False)
        session.add(active)
        session.add(inactive)
        session.commit()

    metrics_service = MagicMock()
    metrics_service.generate_for_persona.return_value = []

    with patch("services.research_analytics_service.RunMetricsService", MagicMock(return_value=metrics_service)):
        rows = ResearchAnalyticsService().refresh_from_zernio()

    assert rows == []
    metrics_service.generate_for_persona.assert_called_once()
    persona_arg = metrics_service.generate_for_persona.call_args.args[0]
    assert persona_arg.id == "active"


def test_refresh_and_summarize_persists_then_reads_latest_snapshots():
    now = datetime.now(timezone.utc)
    with Session(get_engine()) as session:
        persona = Persona(id="p1", tiktok_account_id="account-1")
        run = Run(status="completed", topic="AI agents", news_category="ai", source_article_title="AI wins")
        session.add(persona)
        session.add(run)
        session.commit()
        session.refresh(run)

        persona_run = PersonaRun(
            run_id=run.id,
            persona_id=persona.id,
            status="completed",
            zernio_post_id="post-ai",
            completed_at=now,
        )
        session.add(persona_run)
        session.commit()
        session.refresh(persona_run)

    metrics_service = MagicMock()

    def generate_for_persona(persona: Persona, *, days: int):
        with Session(get_engine()) as session:
            persona_run = session.exec(select(PersonaRun).where(PersonaRun.persona_id == persona.id)).one()
            row = RunMetrics(
                run_id=persona_run.run_id,
                persona_run_id=persona_run.id,
                persona_id=persona.id,
                zernio_post_id="post-ai",
                fetched_at=now,
                views=1000,
                shares=30,
                saves=10,
                engagement_rate=0.12,
                post_age_hours=2,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return [row]

    metrics_service.generate_for_persona.side_effect = generate_for_persona

    with patch("services.research_analytics_service.RunMetricsService", MagicMock(return_value=metrics_service)):
        summary = ResearchAnalyticsService().refresh_and_summarize()

    assert summary["top_categories"][0]["name"] == "ai"
    assert summary["recent_winners"][0]["views"] == 1000
