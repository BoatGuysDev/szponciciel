from datetime import date
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

Current date: {date.today().isoformat()}
Source article title: {state["article_title"]}
Source article URL: {state["article_url"]}
Source article content:
{state.get("article_content") or "No article content was provided."}

Language: {state["persona_language"]}
Style: {state["persona_style"]}
Tone: {state["persona_tone"]}
Story mode: {state["story_mode"]}

Script:
{state["draft_script"]}"""

    parsed = call_agent(CRITIC_SYSTEM_PROMPT, CriticAgentResponseFormat, prompt=prompt)

    review: Review = {
        "mode_compliance_score": parsed.mode_compliance_score,
        "fact_policy_score": parsed.fact_policy_score,
        "persona_fit_score": parsed.persona_fit_score,
        "language_score": parsed.language_score,
        "narrative_confidence_score": parsed.narrative_confidence_score,
        "catchiness_score": parsed.catchiness_score,
        "needs_revision": parsed.needs_revision,
        "diagnostic_reasoning": parsed.diagnostic_reasoning,
        "corrections": parsed.corrections,
    }

    return {
        "review": review,
        "iterations": state["iterations"] + 1,
    }
