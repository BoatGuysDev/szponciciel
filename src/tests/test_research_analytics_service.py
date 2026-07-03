from datetime import datetime, timezone

import pytest
from sqlmodel import Session

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
