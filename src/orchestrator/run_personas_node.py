import random
from datetime import datetime, timezone

import structlog
from sqlmodel import Session

from db import get_engine
from logging_config import get_logger
from models import Persona, PersonaRun
from nodes.persona_graph.graph import persona_graph
from orchestrator.state import OrchestratorState, PersonaOutcome
from utils.logging import describe_exception, log_exception

log = get_logger(__name__)


def run_personas_node(state: OrchestratorState) -> OrchestratorState:
    """Runs the per-persona pipeline for every selected persona, sequentially.

    A failure in one persona is recorded and does not abort the others.
    """

    run_id = state["run_id"]
    persona_ids = state.get("persona_ids") or []
    compiled = persona_graph()
    outcomes: list[PersonaOutcome] = []

    for persona_id in persona_ids:
        with Session(get_engine()) as session:
            persona = session.get(Persona, persona_id)
            if not persona:
                outcomes.append(
                    {
                        "persona_id": persona_id,
                        "status": "failed",
                        "error_message": "Persona not found.",
                    }
                )
                continue
            story_mode = "fictional_news" if random.random() < persona.fictional_news_ratio else "real_news"
            persona_run = PersonaRun(
                run_id=run_id,
                persona_id=persona_id,
                status="running",
                story_mode=story_mode,
                started_at=datetime.now(timezone.utc),
            )
            session.add(persona_run)
            session.commit()
            session.refresh(persona_run)
            persona_run_id = persona_run.id

        structlog.contextvars.bind_contextvars(run_id=run_id, persona_id=persona_id)
        log.info("persona.start", story_mode=story_mode)

        try:
            result = compiled.invoke(
                {
                    "run_id": run_id,
                    "persona_id": persona_id,
                    "story_mode": story_mode,
                    "video_strategy": "stock",
                    "source_article_url": state.get("source_article_url"),
                    "source_article_title": state.get("source_article_title"),
                    "source_article_content": state.get("source_article_content"),
                },
                config={
                    "run_name": f"persona:{persona_id}",
                    "metadata": {"run_id": run_id, "persona_id": persona_id},
                    "tags": [story_mode],
                },
            )
        except Exception as exc:
            log_exception(log, "persona.pipeline_failed", exc)
            result = {
                "is_fatal_error": True,
                "error_message": f"Persona pipeline failed: {describe_exception(exc)}",
            }

        status = "failed" if result.get("is_fatal_error") else "completed"
        if status == "failed":
            log.error("persona.failed", error=result.get("error_message"))
        else:
            log.info("persona.completed", post_id=result.get("tiktok_post_id"))
        structlog.contextvars.clear_contextvars()

        with Session(get_engine()) as session:
            persona_run = session.get(PersonaRun, persona_run_id)
            persona_run.status = status
            persona_run.narration = result.get("narration")
            persona_run.tiktok_caption = result.get("tiktok_caption")
            persona_run.audio_path = result.get("audio_path")
            persona_run.video_category = result.get("video_category")
            persona_run.background_video_path = result.get("background_video_path")
            persona_run.output_video_path = result.get("output_video_path")
            persona_run.tiktok_post_id = result.get("tiktok_post_id")
            persona_run.error_message = result.get("error_message")
            persona_run.completed_at = datetime.now(timezone.utc)
            session.add(persona_run)
            session.commit()

        outcomes.append(
            {
                "persona_id": persona_id,
                "persona_run_id": persona_run_id,
                "status": status,
                "tiktok_post_id": result.get("tiktok_post_id"),
                "error_message": result.get("error_message"),
            }
        )

    return {"outcomes": outcomes}
