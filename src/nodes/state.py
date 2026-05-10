from typing import Literal, TypedDict


class PersonaRunState(TypedDict):
    run_id: str
    persona_id: str
    content_type: Literal["real", "fake"]
    video_strategy: Literal["stock", "ai"]
    narration: str
    tiktok_caption: str
    hashtags: list[str]
    word_timings: list[dict]  # each dict: {"text": str, "start": float, "end": float}
    audio_path: str  # runs/{run_id}/{persona_id}/speech.wav
    video_category: str
    background_video_path: str
    output_video_path: str  # runs/{run_id}/{persona_id}/output.mp4
    tiktok_post_id: str | None
    is_fatal_error: bool
    error_message: str | None
