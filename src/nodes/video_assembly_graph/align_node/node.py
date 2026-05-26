from pathlib import Path
from typing import TypedDict

from config import settings
from nodes.video_assembly_graph.transforms import transcribe_and_align

from nodes.state import PersonaRunState, WordTiming


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
    except Exception as e:
        return {
            "is_fatal_error": True,
            "error_message": f"WhisperX alignment failed: {e}",
        }

    return {
        "word_timings": [
            {"text": w.text, "start": w.start, "end": w.end} for w in words
        ]
    }
