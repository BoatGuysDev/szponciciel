import logging
import os
from typing import TypedDict

from pydantic import ValidationError
from sqlmodel import select, Session

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain.messages import HumanMessage

from src.db import get_engine
from src.models import Persona
from .response_format import CaptionAgentResponseFormat

from .system_prompt import CAPTION_SYSTEM_PROMPT
from ..state import PersonaRunState

log = logging.getLogger(__name__)
CAPTION_MAX_CHARS = 2200


class CaptionResult(TypedDict, total=False):
    tiktok_caption: str
    hashtags: list[str]
    is_fatal_error: bool
    error_message: str | None


def _truncate_caption(caption: str) -> str:
    if len(caption) <= CAPTION_MAX_CHARS:
        return caption

    log.warning(
        "Caption exceeded %d chars (got %d); truncating.",
        CAPTION_MAX_CHARS,
        len(caption),
    )
    cut = caption[:CAPTION_MAX_CHARS]
    last_space = cut.rfind(" ")
    if last_space >= CAPTION_MAX_CHARS - 50:
        cut = cut[:last_space]
    return cut.rstrip()


def caption_node(state: PersonaRunState) -> CaptionResult:
    """Generates the TikTok post caption and hashtags from the narration."""

    with Session(get_engine()) as session:
        persona = session.exec(
            select(Persona).where(Persona.id == state["persona_id"])
        ).first()
        if not persona:
            return {
                "is_fatal_error": True,
                "error_message": f"Persona with id {state['persona_id']} not found.",
            }

    if not all([state.get("narration"), persona.language, persona.style, persona.tone]):
        return {
            "is_fatal_error": True,
            "error_message": "Missing required information to create caption.",
        }

    agent = create_agent(
        model=ChatGoogleGenerativeAI(model=os.getenv("MODEL", "gemini-2.5-flash-lite")),
        system_prompt=CAPTION_SYSTEM_PROMPT,
        response_format=CaptionAgentResponseFormat,
    )

    prompt = f"""
        Create a TikTok post caption for the following narration: {state["narration"]}

        The caption must be in {persona.language} and match the following style and tone: {persona.style}, {persona.tone}.
    """

    response = agent.invoke({"messages": [HumanMessage(content=prompt)]})

    output = response.get("structured_response")
    if output:
        try:
            parsed_output = CaptionAgentResponseFormat.model_validate(output)
        except ValidationError as error:
            log.warning("Invalid structured caption response: %s", error)
            return {
                "is_fatal_error": True,
                "error_message": "Failed to parse agent response.",
            }
    else:
        try:
            parsed_output = CaptionAgentResponseFormat.model_validate_json(
                response["messages"][-1].content
            )
        except (ValidationError, KeyError, IndexError, TypeError, AttributeError) as e:
            log.warning("Caption agent fallback parse failed: %s", e)
            return {
                "is_fatal_error": True,
                "error_message": "Failed to parse agent response.",
            }

    caption = _truncate_caption(parsed_output.caption)
    hashtags = parsed_output.hashtags

    return {
        "tiktok_caption": caption,
        "hashtags": hashtags,
    }
