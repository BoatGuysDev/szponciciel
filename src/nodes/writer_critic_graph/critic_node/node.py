from typing import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain.messages import HumanMessage

from config import settings
from nodes.writer_critic_graph.state import Review, WriterCriticState
from nodes.writer_critic_graph.critic_node.response_format import (
    CriticAgentResponseFormat,
)
from nodes.writer_critic_graph.critic_node.system_prompt import CRITIC_SYSTEM_PROMPT


class CriticResult(TypedDict, total=False):
    review: Review
    iterations: int
    is_fatal_error: bool
    error_message: str | None


def critic_node(state: WriterCriticState) -> CriticResult:
    """Reviews the draft script and returns a reliability score and corrections."""

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
        response = agent.invoke({"messages": [HumanMessage(content=prompt)]})
    except Exception as e:
        return {
            "is_fatal_error": True,
            "error_message": f"Critic agent failed: {e}",
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
