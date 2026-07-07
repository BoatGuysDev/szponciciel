import time
from pathlib import Path
from typing import TypedDict

import requests
from sqlmodel import Session, select
from zernio import Zernio

from config import settings
from db import get_engine
from models import Persona, Run
from nodes.state import PersonaRunState


class UploadResult(TypedDict, total=False):
    zernio_post_id: str
    is_fatal_error: bool
    error_message: str | None


_client: Zernio | None = None


def _build_zernio_metadata(state: PersonaRunState, run: Run, persona: Persona) -> dict:
    """Metadata saved with Zernio posts so another local DB can sync them later."""

    return {
        "schema_version": 1,
        "app": "szponciciel",
        "run": {
            "id": state["run_id"],
            "topic": run.topic or state.get("topic"),
            "news_category": run.news_category or state.get("news_category"),
            "research_query": run.research_query or state.get("research_query"),
            "source_article_url": run.source_article_url or state.get("source_article_url"),
            "source_article_title": run.source_article_title or state.get("source_article_title"),
        },
        "persona_run": {
            "id": state.get("persona_run_id"),
            "story_mode": state.get("story_mode"),
        },
        "persona": {
            "id": state["persona_id"],
            "tiktok_account_id": persona.tiktok_account_id,
            "language": persona.language,
            "style": persona.style,
            "tone": persona.tone,
        },
        "generation": {
            "llm_model": settings.llm_model,
            "writer_critic_max_iters": settings.writer_critic_max_iters,
            "base_script": state.get("base_script") or run.base_script,
            "narration": state.get("narration"),
            "caption": state.get("tiktok_caption"),
            "hashtags": state.get("hashtags") or [],
            "video_category": state.get("video_category"),
        },
    }


def upload_node(state: PersonaRunState) -> UploadResult:
    with Session(get_engine()) as session:
        persona = session.exec(select(Persona).where(Persona.id == state["persona_id"])).first()

        if not persona:
            return {
                "is_fatal_error": True,
                "error_message": f"Persona with id {state['persona_id']} not found.",
            }

        run = session.exec(select(Run).where(Run.id == state["run_id"])).first()
        if not run:
            return {
                "is_fatal_error": True,
                "error_message": f"Run with id {state['run_id']} not found.",
            }

    filename = f"{state['run_id']}_{state['persona_id']}_{time.time_ns()}.mp4"

    global _client
    if _client is None:
        _client = Zernio(api_key=settings.zernio_api_key)

    presigned_result = _client.media.get_media_presigned_url(filename=filename, content_type="video/mp4")

    upload_url = presigned_result["uploadUrl"]
    public_url = presigned_result["publicUrl"]

    video_path = Path(state["output_video_path"])
    if not video_path.exists():
        return {
            "is_fatal_error": True,
            "error_message": f"File not found: {video_path}",
        }
    elif not video_path.is_file():
        return {
            "is_fatal_error": True,
            "error_message": f"Not a file: {video_path}",
        }
    elif video_path.suffix.lower() != ".mp4":
        return {
            "is_fatal_error": True,
            "error_message": f"Invalid file type: {video_path.suffix}",
        }

    with video_path.open("rb") as f:
        upload_video_response = requests.put(upload_url, data=f.read(), headers={"Content-Type": "video/mp4"})

    if not upload_video_response.ok:
        return {
            "is_fatal_error": True,
            "error_message": f"Failed to upload video: {upload_video_response.text}",
        }

    description = state["tiktok_caption"]
    if state["hashtags"]:
        description += f"\n\n{' '.join(state['hashtags'])}"

    response = _client.posts.create(
        media_items=[{"url": public_url, "type": "video"}],
        content=description,
        hashtags=state["hashtags"],
        platforms=[{"platform": "tiktok", "accountId": persona.tiktok_account_id}],
        publish_now=True,
        metadata=_build_zernio_metadata(state, run, persona),
    )

    return {"zernio_post_id": response.post.field_id}
