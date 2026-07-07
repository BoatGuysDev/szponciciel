from pathlib import Path
from typing import Literal, TypedDict

from langgraph.graph import END


def persona_run_dir(state: "PersonaRunState") -> Path:
    return Path("runs") / state["run_id"] / state["persona_id"]


def end_if_fatal(next_node: str):
    """Conditional-edge router: stop at END on a fatal error, else go to next_node.

    Keeps a failed node's error_message intact instead of letting a downstream
    node crash on the missing state it expected.
    """

    def router(state: "PersonaRunState") -> str:
        return END if state.get("is_fatal_error") else next_node

    return router


class WordTiming(TypedDict):
    text: str
    start: float
    end: float


class PersonaRunState(TypedDict):
    run_id: str
    persona_run_id: str
    persona_id: str
    story_mode: Literal["real_news", "fictional_news"]
    topic: str | None
    news_category: str | None
    research_query: str | None
    video_strategy: Literal["stock", "ai"]
    source_article_url: str
    source_article_title: str
    source_article_content: str
    base_script: str
    narration: str
    tiktok_caption: str
    hashtags: list[str]
    word_timings: list[WordTiming]
    audio_path: str  # runs/{run_id}/{persona_id}/speech.wav
    video_category: str
    background_video_path: str
    output_video_path: str  # runs/{run_id}/{persona_id}/output.mp4
    zernio_post_id: str | None
    is_fatal_error: bool
    error_message: str | None
