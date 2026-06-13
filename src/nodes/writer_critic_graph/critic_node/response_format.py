from pydantic import BaseModel, Field


class CriticAgentResponseFormat(BaseModel):
    """Expected output format from the critic agent."""

    mode_compliance_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "How well the script follows the requested story mode. For fictional_news, "
            "penalize prediction, hypothetical, dream-scenario, or 'imagine if' framing."
        ),
    )
    fact_policy_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "For real_news, how well material claims are grounded in the source article. "
            "For fictional_news, how well the script works as coherent fabricated news "
            "without accidentally turning into speculation or source-summary."
        ),
    )
    persona_fit_score: float = Field(
        ge=0.0,
        le=1.0,
        description="How well the script matches the persona style and tone.",
    )
    language_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Grammar and linguistic correctness in the declared persona language.",
    )
    narrative_confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="How confidently and unambiguously the script presents its story without unwanted hedging.",
    )
    catchiness_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "How well the script works as short-form spoken content: hook strength, "
            "punchy delivery, pacing, and TikTok appropriateness."
        ),
    )
    needs_revision: bool = Field(description="True when the writer should revise the draft before approval.")
    diagnostic_reasoning: str = Field(
        max_length=2_000,
        description=(
            "Brief diagnostic rationale explaining the scores and why revision is or is "
            "not needed. This is for debugging, not hidden reasoning."
        ),
    )
    corrections: str = Field(
        max_length=2_000,
        description=(
            "Concrete, actionable feedback the writer can apply on the next "
            "iteration. Empty string when the script passes all rubrics cleanly."
        ),
    )
