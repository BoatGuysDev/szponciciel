from typing import TypedDict


class Review(TypedDict):
    mode_compliance_score: float
    fact_policy_score: float
    persona_fit_score: float
    language_score: float
    narrative_confidence_score: float
    catchiness_score: float
    needs_revision: bool
    diagnostic_reasoning: str
    corrections: str


class WriterCriticState(TypedDict):
    article_url: str
    article_title: str
    article_content: str | None

    persona_language: str
    persona_style: str
    persona_tone: str
    story_mode: str

    draft_script: str | None
    review: Review | None
    iterations: int

    is_fatal_error: bool
    error_message: str | None
