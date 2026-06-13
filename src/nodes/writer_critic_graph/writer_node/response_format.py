from pydantic import BaseModel, Field


class WriterAgentResponseFormat(BaseModel):
    """Expected output format from the writer agent."""

    draft_script: str = Field(description="The generated TikTok script.")
