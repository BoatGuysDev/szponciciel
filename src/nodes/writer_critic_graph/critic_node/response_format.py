from pydantic import BaseModel, Field


class CriticAgentResponseFormat(BaseModel):
    """Expected output format from the critic agent."""

    coherence_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "How coherent the script is between real and fabricated content. "
            "Satirical or fictional elements must not contradict the factual ones "
            "and must respect the persona's real_news_ratio."
        ),
    )
    grammar_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Grammar and linguistic correctness in the declared persona language. "
            "Penalize typos, malformed sentences, and unintended language mixing."
        ),
    )
    unambiguity_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "How unambiguous the script is. Penalize vague claims, hedging, or "
            "phrasing that leaves the viewer in doubt about what is being said."
        ),
    )
    catchiness_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "How well the script works as short-form spoken content: hook strength, "
            "punchy delivery, pacing, and TikTok appropriateness."
        ),
    )
    corrections: str = Field(
        description=(
            "Concrete, actionable feedback the writer can apply on the next "
            "iteration. Empty string when the script passes all rubrics cleanly."
        ),
    )
