from typing import TypedDict


class Review(TypedDict):
    coherence_score: float
    grammar_score: float
    unambiguity_score: float
    catchiness_score: float
    corrections: str


class WriterCriticState(TypedDict):
    article_url: str
    article_title: str

    persona_language: str
    persona_style: str
    persona_tone: str
    real_news_ratio: float

    draft_script: str | None
    review: Review | None
    iterations: int

    is_fatal_error: bool
    error_message: str | None
