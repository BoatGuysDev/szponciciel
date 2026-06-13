from typing import TypedDict

from sqlmodel import Session, select

from db import get_engine
from logging_config import get_logger
from models import Persona
from nodes.caption_node.response_format import CaptionAgentResponseFormat
from nodes.caption_node.system_prompt import CAPTION_SYSTEM_PROMPT
from nodes.state import PersonaRunState
from utils.agent_utils import call_agent

log = get_logger(__name__)
CAPTION_MAX_CHARS = 2200
WORD_BOUNDARY_WINDOW = 50


class CaptionResult(TypedDict, total=False):
    tiktok_caption: str
    hashtags: list[str]
    is_fatal_error: bool
    error_message: str | None


def _truncate_caption(caption: str) -> str:
    if len(caption) <= CAPTION_MAX_CHARS:
        return caption

    log.warning("caption.truncated", max_chars=CAPTION_MAX_CHARS, length=len(caption))

    cut = caption[:CAPTION_MAX_CHARS]
    last_space = cut.rfind(" ")
    if last_space >= CAPTION_MAX_CHARS - WORD_BOUNDARY_WINDOW:
        cut = cut[:last_space]

    return cut.rstrip()


def caption_node(state: PersonaRunState) -> CaptionResult:
    """Generates the TikTok post caption and hashtags from the narration."""

    result = {
        "tiktok_caption": "",
        "hashtags": [],
        "is_fatal_error": False,
        "error_message": None,
    }

    with Session(get_engine()) as session:
        persona = session.exec(select(Persona).where(Persona.id == state["persona_id"])).first()
        if not persona:
            result["is_fatal_error"] = True
            result["error_message"] = f"Persona with id {state['persona_id']} not found."
            return result

    if not all([state.get("narration"), persona.language, persona.style, persona.tone]):
        result["is_fatal_error"] = True
        result["error_message"] = "Missing required information to create caption."
        return result

    prompt = f"""
        Create a TikTok post caption for the following narration: {state["narration"]}

        Story mode: {state.get("story_mode", "real_news")}.
        The caption must be in {persona.language} and match the following style and tone: {persona.style}, {persona.tone}.
    """

    parsed_output = call_agent(CAPTION_SYSTEM_PROMPT, CaptionAgentResponseFormat, prompt=prompt)

    result["tiktok_caption"] = _truncate_caption(parsed_output.caption)
    result["hashtags"] = parsed_output.hashtags

    return result
