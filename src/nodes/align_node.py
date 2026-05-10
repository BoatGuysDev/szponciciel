from pathlib import Path

from config import COMPUTE_DEVICE, WHISPER_MODEL
from merge_captions import transcribe_and_align

from nodes.state import PersonaRunState


def align_node(state: PersonaRunState) -> dict:
    """Runs WhisperX forced alignment on speech.wav and stores word timings in state."""
    audio_path = Path(state["audio_path"])
    if not audio_path.is_file():
        return {
            "is_fatal_error": True,
            "error_message": f"Audio file not found: {audio_path}",
        }

    try:
        words = transcribe_and_align(
            audio_path, device=COMPUTE_DEVICE, model_size=WHISPER_MODEL
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
