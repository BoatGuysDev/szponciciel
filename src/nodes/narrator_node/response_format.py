from pydantic import BaseModel, Field


class NarratorAgentResponseFormat(BaseModel):
    """Expected output format from the narration generation agent."""

    narration: str = Field(description="The generated narration text.")
    diagnostic_reasoning: str = Field(
        description=(
            "Brief diagnostic rationale explaining how the narration preserves the "
            "script, story mode, persona style, and tone. This is for debugging, not hidden reasoning."
        ),
    )
