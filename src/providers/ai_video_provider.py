from pathlib import Path

from providers.video_provider import VideoRequest


class AIVideoProvider:
    """
    Stub for future AI-generated video backends (Kling AI, RunwayML, Pika, HeyGen).

    When implemented, this provider will build a generation prompt from
    `request.narration` and `request.tiktok_caption`, use `request.category`
    as a visual style hint, call the remote generation API, poll until the
    video is ready, download it to a local temp path, and return that path.
    """

    def get_video(self, request: VideoRequest) -> Path:
        raise NotImplementedError(
            "AIVideoProvider is not yet implemented. "
            "Set video_strategy='stock' to use StockVideoProvider."
        )
