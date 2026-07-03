from typing import TypedDict


class PersonaOutcome(TypedDict, total=False):
    persona_id: str
    persona_run_id: str
    status: str  # "completed" | "failed"
    zernio_post_id: str | None
    error_message: str | None


class OrchestratorState(TypedDict, total=False):
    prompt: str | None  # raw user instruction / meta-prompt
    topic: str | None  # parsed topic, or None for a generic category sweep
    run_id: str
    source_article_url: str
    source_article_title: str
    source_article_content: str
    news_category: str | None
    research_query: str | None
    persona_ids: list[str]
    outcomes: list[PersonaOutcome]
    is_fatal_error: bool
    error_message: str | None
