from typing import TypedDict

from nodes.writer_critic_graph.critic_node.response_format import (
    CriticAgentResponseFormat,
)
from nodes.writer_critic_graph.critic_node.system_prompt import CRITIC_SYSTEM_PROMPT
from nodes.writer_critic_graph.state import Review, WriterCriticState
from utils.agent_utils import call_agent


class CriticResult(TypedDict, total=False):
    review: Review
    iterations: int
    is_fatal_error: bool
    error_message: str | None


def critic_node(state: WriterCriticState) -> CriticResult:
    """Reviews the draft script and produces a summary with scores and corrections."""

    prompt = f"""Review the following TikTok script.

Language: {state["persona_language"]}
Style: {state["persona_style"]}
Tone: {state["persona_tone"]}
Real news ratio: {state["real_news_ratio"]}

Script:
{state["draft_script"]}"""

    parsed = call_agent(CRITIC_SYSTEM_PROMPT, CriticAgentResponseFormat, prompt=prompt)

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
