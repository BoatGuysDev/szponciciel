from typing import TypedDict


class PersonaOutcome(TypedDict, total=False):
    persona_id: str
    persona_run_id: str
    status: str  # "completed" | "failed"
    tiktok_post_id: str | None
    error_message: str | None


class OrchestratorState(TypedDict, total=False):
    prompt: str | None  # raw user instruction / meta-prompt
    topic: str | None  # parsed topic, or None for a generic category sweep
    run_id: str
    persona_ids: list[str]
    outcomes: list[PersonaOutcome]
    is_fatal_error: bool
    error_message: str | None
