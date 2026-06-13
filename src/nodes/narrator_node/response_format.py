from pydantic import BaseModel, Field


class NarratorAgentResponseFormat(BaseModel):
    """Expected output format from the narration generation agent."""

    narration: str = Field(description="The generated narration text.")
