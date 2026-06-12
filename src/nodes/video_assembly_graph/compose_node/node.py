from pathlib import Path
from typing import TypedDict

from logging_config import get_logger
from nodes.state import PersonaRunState, persona_run_dir
from nodes.video_assembly_graph.transforms import Word, compose
from utils.logging import describe_exception, log_exception

log = get_logger(__name__)


class ComposeResult(TypedDict, total=False):
    output_video_path: str
    is_fatal_error: bool
    error_message: str | None


def compose_node(state: PersonaRunState) -> ComposeResult:
    out_path = persona_run_dir(state) / "output.mp4"

    try:
        words = [Word(text=w["text"], start=w["start"], end=w["end"]) for w in state["word_timings"]]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        compose(
            Path(state["background_video_path"]),
            Path(state["audio_path"]),
            words,
            out_path,
        )
    except Exception as exc:
        log_exception(
            log,
            "compose.failed",
            exc,
            background_video_path=state.get("background_video_path"),
            audio_path=state.get("audio_path"),
        )
        return {
            "is_fatal_error": True,
            "error_message": f"Video composition failed: {describe_exception(exc)}",
        }

    return {"output_video_path": str(out_path)}
