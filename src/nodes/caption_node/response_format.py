from pydantic import BaseModel, Field


class CaptionAgentResponseFormat(BaseModel):
    """Expected output format from the caption generation agent."""

    caption: str = Field(description="The generated TikTok caption.")
    hashtags: list[str] = Field(description="List of relevant hashtags for the TikTok post.")
