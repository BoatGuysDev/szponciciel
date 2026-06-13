from pydantic import BaseModel, Field


class WriterAgentResponseFormat(BaseModel):
    """Expected output format from the writer agent."""

    draft_script: str = Field(description="The generated TikTok script.")
    diagnostic_reasoning: str = Field(
        description=(
            "Brief diagnostic rationale explaining how the draft follows the requested "
            "story mode, persona style, and tone. This is for debugging, not hidden reasoning."
        ),
    )
