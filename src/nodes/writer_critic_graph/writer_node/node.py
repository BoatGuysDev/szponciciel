from typing import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

from config import settings
from nodes.writer_critic_graph.state import WriterCriticState
from nodes.writer_critic_graph.writer_node.system_prompt import WRITER_SYSTEM_PROMPT
from nodes.writer_critic_graph.writer_node.tools import fetch_article_content
from nodes.utils import AgentResponseError, invoke_agent


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

    agent = create_agent(
        model=ChatGoogleGenerativeAI(model=settings.llm_model),
        system_prompt=WRITER_SYSTEM_PROMPT,
        tools=[fetch_article_content],
    )

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

    try:
        script = _truncate_script(invoke_agent(agent, prompt))
    except AgentResponseError as e:
        return {
            "is_fatal_error": True,
            "error_message": f"Writer agent failed: {e}",
        }

    return {
        "draft_script": script,
    }
