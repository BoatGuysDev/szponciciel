from pathlib import Path
from typing import TypedDict

from config import settings
from logging_config import get_logger
from nodes.state import PersonaRunState, WordTiming
from nodes.video_assembly_graph.transforms import transcribe_and_align
from utils.logging import describe_exception, log_exception

log = get_logger(__name__)


class AlignResult(TypedDict, total=False):
    word_timings: list[WordTiming]
    is_fatal_error: bool
    error_message: str | None


def align_node(state: PersonaRunState) -> AlignResult:
    audio_path_value = state.get("audio_path")
    if not audio_path_value:
        return {
            "is_fatal_error": True,
            "error_message": f"Audio file not found: {audio_path_value}",
        }
    audio_path = Path(audio_path_value)
    if not audio_path.is_file():
        return {
            "is_fatal_error": True,
            "error_message": f"Audio file not found: {audio_path}",
        }

    try:
        words = transcribe_and_align(
            audio_path,
            device=settings.compute_device,
            model_size=settings.whisper_model,
        )
    except Exception as exc:
        log_exception(log, "alignment.failed", exc, audio_path=str(audio_path))
        return {
            "is_fatal_error": True,
            "error_message": f"WhisperX alignment failed: {describe_exception(exc)}",
        }

    return {"word_timings": [{"text": w.text, "start": w.start, "end": w.end} for w in words]}
