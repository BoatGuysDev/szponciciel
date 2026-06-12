from typing import TypedDict

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from config import settings
from logging_config import get_logger
from nodes.utils import AgentResponseError, invoke_agent_response
from nodes.writer_critic_graph.critic_node.response_format import (
    CriticAgentResponseFormat,
)
from nodes.writer_critic_graph.critic_node.system_prompt import CRITIC_SYSTEM_PROMPT
from nodes.writer_critic_graph.state import Review, WriterCriticState
from utils.logging import describe_exception, log_exception

log = get_logger(__name__)


class CriticResult(TypedDict, total=False):
    review: Review
    iterations: int
    is_fatal_error: bool
    error_message: str | None


def critic_node(state: WriterCriticState) -> CriticResult:
    """Reviews the draft script and produces a summary with scores and corrections."""

    agent = create_agent(
        model=ChatGoogleGenerativeAI(model=settings.llm_model),
        system_prompt=CRITIC_SYSTEM_PROMPT,
        response_format=CriticAgentResponseFormat,
    )

    prompt = f"""Review the following TikTok script.

Language: {state["persona_language"]}
Style: {state["persona_style"]}
Tone: {state["persona_tone"]}
Real news ratio: {state["real_news_ratio"]}

Script:
{state["draft_script"]}"""

    try:
        response = invoke_agent_response(agent, prompt)
    except AgentResponseError as exc:
        log_exception(log, "critic.agent_failed", exc, iterations=state["iterations"])
        return {
            "is_fatal_error": True,
            "error_message": f"Critic agent failed: {describe_exception(exc)}",
        }

    parsed: CriticAgentResponseFormat | None = response.get("structured_response")
    if parsed is None:
        return {
            "is_fatal_error": True,
            "error_message": "Failed to parse critic response.",
        }

    review: Review = {
        "coherence_score": parsed.coherence_score,
        "grammar_score": parsed.grammar_score,
        "unambiguity_score": parsed.unambiguity_score,
        "catchiness_score": parsed.catchiness_score,
        "corrections": parsed.corrections,
    }

    return {
        "review": review,
        "iterations": state["iterations"] + 1,
    }
