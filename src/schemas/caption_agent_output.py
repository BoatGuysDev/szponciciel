from pydantic import BaseModel, Field


class CaptionAgentOutput(BaseModel):
    """Expected output format from the caption generation agent."""

    tiktok_caption: str = Field(description="The generated TikTok caption.")
    hashtags: list[str] = Field(
        description="List of relevant hashtags for the TikTok post."
    )
