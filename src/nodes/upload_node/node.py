import time
from pathlib import Path
from typing import TypedDict

import requests
from requests import RequestException
from sqlmodel import Session, select
from zernio import Zernio, ZernioAPIError

from config import settings
from db import get_engine
from logging_config import get_logger
from models import Persona
from nodes.state import PersonaRunState
from utils.logging import describe_exception, log_exception

log = get_logger(__name__)


class UploadResult(TypedDict, total=False):
    tiktok_post_id: str
    is_fatal_error: bool
    error_message: str | None


_client: Zernio | None = None


def upload_node(state: PersonaRunState) -> UploadResult:
    with Session(get_engine()) as session:
        persona = session.exec(select(Persona).where(Persona.id == state["persona_id"])).first()

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
        presigned_result = _client.media.get_media_presigned_url(filename=filename, content_type="video/mp4")
    except ZernioAPIError as exc:
        log_exception(log, "upload.presigned_url_failed", exc, run_id=state["run_id"], persona_id=state["persona_id"])
        return {
            "is_fatal_error": True,
            "error_message": f"Failed to get presigned URL: {describe_exception(exc)}",
        }
    except Exception as exc:
        log_exception(log, "upload.presigned_url_failed", exc, run_id=state["run_id"], persona_id=state["persona_id"])
        return {
            "is_fatal_error": True,
            "error_message": f"Failed to get presigned URL: {describe_exception(exc)}",
        }

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

    try:
        with video_path.open("rb") as f:
            upload_video_response = requests.put(upload_url, data=f.read(), headers={"Content-Type": "video/mp4"})
    except RequestException as exc:
        log_exception(log, "upload.video_put_failed", exc, run_id=state["run_id"], persona_id=state["persona_id"], video_path=str(video_path))
        return {
            "is_fatal_error": True,
            "error_message": f"Request error: {describe_exception(exc)}",
        }
    except Exception as exc:
        log_exception(log, "upload.video_put_failed", exc, run_id=state["run_id"], persona_id=state["persona_id"], video_path=str(video_path))
        return {
            "is_fatal_error": True,
            "error_message": f"Request error: {describe_exception(exc)}",
        }

    if not upload_video_response.ok:
        return {
            "is_fatal_error": True,
            "error_message": f"Failed to upload video: {upload_video_response.text}",
        }

    try:
        response = _client.posts.create(
            media_items=[{"url": public_url, "type": "video"}],
            content=state["tiktok_caption"],
            hashtags=state["hashtags"],
            platforms=[{"platform": "tiktok", "accountId": persona.tiktok_account_id}],
            publish_now=True,
        )
    except ZernioAPIError as exc:
        log_exception(log, "upload.create_post_failed", exc, run_id=state["run_id"], persona_id=state["persona_id"])
        return {
            "is_fatal_error": True,
            "error_message": f"Failed to create post: {describe_exception(exc)}",
        }
    except Exception as exc:
        log_exception(log, "upload.create_post_failed", exc, run_id=state["run_id"], persona_id=state["persona_id"])
        return {
            "is_fatal_error": True,
            "error_message": f"Failed to create post: {describe_exception(exc)}",
        }

    return {"tiktok_post_id": response.post.field_id}
