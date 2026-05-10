import logging
import re

from sqlmodel import Session, select
from TTS.api import TTS
from dotenv import load_dotenv

from config import COMPUTE_DEVICE
from db import get_engine
from models import Persona
from nodes.state import PersonaRunState, persona_run_dir

load_dotenv()

log = logging.getLogger(__name__)
_tts: TTS | None = None


def _sanitize_for_tts(text: str) -> str:
    # XTTS v2 vocalizes periods as "dot"; replace sentence-ending periods with a space
    return re.sub(r"\.\s+", " ", text).rstrip(".")


def tts_node(state: PersonaRunState) -> dict[str, str | bool]:
    if not state["narration"]:
        return {
            "is_fatal_error": True,
            "error_message": "Narration text is empty.",
        }

    with Session(get_engine()) as session:
        persona = session.exec(
            select(Persona).where(Persona.id == state["persona_id"])
        ).first()

        if not persona:
            return {
                "is_fatal_error": True,
                "error_message": f"Persona with id {state['persona_id']} not found.",
            }

    out_path = persona_run_dir(state) / "speech.wav"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    kwargs = {
        "text": _sanitize_for_tts(state["narration"]),
        "file_path": str(out_path),
        "language": persona.language or "en",
    }
    if persona.voice_speaker_wav is not None:
        kwargs["speaker_wav"] = persona.voice_speaker_wav
    else:
        kwargs["speaker"] = (
            persona.voice_speaker
        )  # If None, the TTS model will choose a default speaker for the language

    global _tts
    if _tts is None:
        _tts = TTS(
            model_name="tts_models/multilingual/multi-dataset/xtts_v2",
            progress_bar=True,
        ).to(COMPUTE_DEVICE)

    try:
        _tts.tts_to_file(**kwargs)
    except Exception as e:
        log.exception("TTS generation failed")
        return {
            "is_fatal_error": True,
            "error_message": f"Error during TTS generation: {str(e)}",
        }

    return {
        "audio_path": str(out_path),
    }
