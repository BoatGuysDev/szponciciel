from pathlib import Path


class AIVideoProvider:
    """
    Stub for future AI-generated video backends (Kling AI, RunwayML, Pika, HeyGen).

    When implemented, this provider will accept a natural-language prompt derived
    from the article/narration, call the remote generation API, poll until the
    video is ready, download it to a local temp path, and return that path.

    The `category` argument maps to a visual style hint passed to the API prompt.
    """

    def get_video(self, category: str) -> Path:
        raise NotImplementedError(
            "AIVideoProvider is not yet implemented. "
            "Set video_strategy='stock' to use StockVideoProvider."
        )
