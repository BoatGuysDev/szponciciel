from typing import TypedDict

from config import settings
from nodes.writer_critic_graph.state import WriterCriticState
from nodes.writer_critic_graph.writer_node.response_format import WriterAgentResponseFormat
from nodes.writer_critic_graph.writer_node.system_prompt import WRITER_SYSTEM_PROMPT
from nodes.writer_critic_graph.writer_node.tools import fetch_article_content
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

    prompt = f"""Write a TikTok script for the following article:

Title: {state["article_title"]}
URL: {state["article_url"]}

Language: {state["persona_language"]}
Style: {state["persona_style"]}
Tone: {state["persona_tone"]}
Real news ratio: {state["real_news_ratio"]}"""

    if state["review"] and state["review"]["corrections"]:
        prompt += (
            f"\n\nIncorporate the following corrections from the previous draft:\n{state['review']['corrections']}"
        )
        prompt += f"\n\nPrevious draft script:\n{state['draft_script']}"

    script = _truncate_script(
        call_agent(
            WRITER_SYSTEM_PROMPT,
            WriterAgentResponseFormat,
            prompt=prompt,
            tools=[fetch_article_content],
        ).draft_script
    )

    return {
        "draft_script": script,
    }
