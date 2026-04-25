from typing import Literal, TypedDict


class PersonaRunState(TypedDict):
    run_id: str
    persona_id: str
    content_type: Literal["real", "fake"]
    video_strategy: Literal["stock", "ai"]
    narration: str
    tiktok_caption: str
    hashtags: list[str]
    audio_path: str  # runs/{run_id}/{persona_id}/speech.wav
    video_category: str
    background_video_path: str
    output_video_path: str  # runs/{run_id}/{persona_id}/output.mp4
    tiktok_post_id: str | None
