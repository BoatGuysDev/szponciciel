from typing import TypedDict


class WriterCriticState(TypedDict):
    article_url: str
    article_title: str

    persona_language: str
    persona_style: str
    persona_tone: str
    real_news_ratio: float

    draft_script: str | None
    reliability_score: float | None
    corrections: str | None
    iterations: int

    is_fatal_error: bool
    error_message: str | None
