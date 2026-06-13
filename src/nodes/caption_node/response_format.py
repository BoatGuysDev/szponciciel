from pydantic import BaseModel, Field


class CaptionAgentResponseFormat(BaseModel):
    """Expected output format from the caption generation agent."""

    caption: str = Field(description="The generated TikTok caption.")
    hashtags: list[str] = Field(description="List of relevant hashtags for the TikTok post.")
    diagnostic_reasoning: str = Field(
        description=(
            "Brief diagnostic rationale explaining how the caption follows the narration, "
            "story mode, persona style, and tone. This is for debugging, not hidden reasoning."
        ),
    )
