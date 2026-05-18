import requests
from pathlib import Path
import time
from typing import TypedDict

from zernio import Zernio, ZernioAPIError
from sqlmodel import Session, select

from db import get_engine
from models import Persona
from config import settings
from nodes.state import PersonaRunState


class UploadResult(TypedDict, total=False):
    is_fatal_error: bool
    error_message: str | None


_client: Zernio | None = None


def upload_node(state: PersonaRunState) -> UploadResult:
    with Session(get_engine()) as session:
        persona = session.exec(
            select(Persona).where(Persona.id == state["persona_id"])
        ).first()

        if not persona:
            return {
                "is_fatal_error": True,
                "error_message": f"Persona with id {state['persona_id']} not found.",
            }

    filename = f"{state['run_id']}_{state['persona_id']}_{time.time_ns()}.mp4"

    global _client
    if _client is None:
        _client = Zernio(api_key=settings.zernio_api_key)

    try:
        presigned_result = _client.media.get_media_presigned_url(
            filename=filename, content_type="video/mp4"
        )
    except ZernioAPIError as e:
        return {
            "is_fatal_error": True,
            "error_message": f"Failed to get presigned URL: {e}",
        }

    upload_url = presigned_result["uploadUrl"]
    public_url = presigned_result["publicUrl"]

    video_path = Path(state["output_video_path"])
    if not video_path.exists():
        return {
            "is_fatal_error": True,
            "error_message": f"File not found: {video_path}",
        }

    with video_path.open("rb") as f:
        upload_video_response = requests.put(
            upload_url, data=f.read(), headers={"Content-Type": "video/mp4"}
        )

    if not upload_video_response.ok:
        return {
            "is_fatal_error": True,
            "error_message": f"Failed to upload video: {upload_video_response.text}",
        }

    try:
        _client.posts.create(
            media_items=[{"url": public_url, "type": "video"}],
            content=state["tiktok_caption"],
            hashtags=state["hashtags"],
            platforms=[{"platform": "tiktok", "accountId": persona.tiktok_account_id}],
            publish_now=True,
        )
    except ZernioAPIError as e:
        return {
            "is_fatal_error": True,
            "error_message": f"Failed to create post: {e}",
        }

    return {}
