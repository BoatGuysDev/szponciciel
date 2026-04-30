import os

from pathlib import Path
from sqlmodel import Session, select
from TTS.api import TTS
from dotenv import load_dotenv

from src.db import get_engine
from src.models import Persona
from .state import PersonaRunState

load_dotenv()

DEVICE = os.getenv("COMPUTE_DEVICE", "cpu")


def tts_node(state: PersonaRunState) -> dict[str, str | bool]:
    """Converts the narration text into speech and saves the audio file."""

    with Session(get_engine()) as session:
        persona = session.exec(
            select(Persona).where(Persona.id == state["persona_id"])
        ).first()

        if not persona:
            return {
                "is_fatal_error": True,
                "error_message": f"Persona with id {state['persona_id']} not found.",
            }

    tts = TTS(
        model_name="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=True
    ).to(DEVICE)

    out_path = Path(f"runs/{state['run_id']}/{state['persona_id']}/speech.wav")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not state["narration"]:
        return {
            "is_fatal_error": True,
            "error_message": "Narration text is empty.",
        }

    kwargs = {
        "text": state["narration"],
        "file_path": str(out_path),
        "language": persona.language or "en",
    }
    if persona.voice_speaker_wav is not None:
        kwargs["speaker_wav"] = persona.voice_speaker_wav
    else:
        kwargs["speaker"] = (
            persona.voice_speaker
        )  # If None, the TTS model will choose a default speaker for the language

    tts.tts_to_file(**kwargs)

    return {
        "audio_path": str(out_path),
    }
