from typing import TypedDict

from sqlmodel import select, Session

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain.messages import HumanMessage

from config import settings
from db import get_engine
from logging_config import get_logger
from models import Persona
from .response_format import CaptionAgentResponseFormat

from .system_prompt import CAPTION_SYSTEM_PROMPT
from ..state import PersonaRunState

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
        persona = session.exec(
            select(Persona).where(Persona.id == state["persona_id"])
        ).first()
        if not persona:
            result["is_fatal_error"] = True
            result["error_message"] = (
                f"Persona with id {state['persona_id']} not found."
            )
            return result

    if not all([state.get("narration"), persona.language, persona.style, persona.tone]):
        result["is_fatal_error"] = True
        result["error_message"] = "Missing required information to create caption."
        return result

    try:
        agent = create_agent(
            model=ChatGoogleGenerativeAI(model=settings.llm_model),
            system_prompt=CAPTION_SYSTEM_PROMPT,
            response_format=CaptionAgentResponseFormat,
        )

        prompt = f"""
        Create a TikTok post caption for the following narration: {state["narration"]}

        The caption must be in {persona.language} and match the following style and tone: {persona.style}, {persona.tone}.
    """

        response = agent.invoke({"messages": [HumanMessage(content=prompt)]})
    except Exception as e:
        result["is_fatal_error"] = True
        result["error_message"] = f"Caption agent failed: {e}"
        return result

    parsed_output = response.get("structured_response")
    if parsed_output is None:
        log.warning("caption.no_structured_response")
        result["is_fatal_error"] = True
        result["error_message"] = "Failed to parse agent response."
        return result

    result["tiktok_caption"] = _truncate_caption(parsed_output.caption)
    result["hashtags"] = parsed_output.hashtags

    return result
