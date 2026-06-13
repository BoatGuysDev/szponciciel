from typing import TypedDict

from config import settings
from nodes.writer_critic_graph.state import WriterCriticState
from nodes.writer_critic_graph.writer_node.response_format import WriterAgentResponseFormat
from nodes.writer_critic_graph.writer_node.system_prompt import WRITER_SYSTEM_PROMPT
from utils.agent_utils import call_agent


class WriterResult(TypedDict, total=False):
    draft_script: str
    is_fatal_error: bool
    error_message: str | None


def _truncate_script(script: str) -> str:
    if len(script) <= settings.max_script_length:
        return script

    suffix = "..."
    truncated_script = script[: settings.max_script_length - len(suffix)].rstrip() + suffix
    return truncated_script


def writer_node(state: WriterCriticState) -> WriterResult:
    """Generates a TikTok script from article data and persona configuration."""

    article_content = (state.get("article_content") or "").strip()
    article_excerpt = article_content[: settings.max_script_length].strip()

    prompt = f"""Write a TikTok script for the following article:

Title: {state["article_title"]}
URL: {state["article_url"]}
Article content:
{article_excerpt or "No article excerpt was provided. Use the title and URL context only."}

Language: {state["persona_language"]}
Style: {state["persona_style"]}
Tone: {state["persona_tone"]}
Story mode: {state["story_mode"]}"""

    if state["review"] and state["review"]["corrections"]:
        prompt += (
            f"\n\nIncorporate the following corrections from the previous draft:\n{state['review']['corrections']}"
        )
        prompt += f"\n\nPrevious critic diagnostic rationale:\n{state['review']['diagnostic_reasoning']}"
        prompt += f"\n\nPrevious draft script:\n{state['draft_script']}"

    script = _truncate_script(
        call_agent(
            WRITER_SYSTEM_PROMPT,
            WriterAgentResponseFormat,
            prompt=prompt,
        ).draft_script
    )

    return {
        "draft_script": script,
    }
