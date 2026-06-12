from moviepy import AudioFileClip, VideoFileClip

from logging_config import get_logger
from nodes.state import PersonaRunState, persona_run_dir
from nodes.video_assembly_graph.transforms import (
    VIDEO_WRITE_KWARGS,
    fit_vertical,
    loop_to_duration,
)
from utils.logging import describe_exception, log_exception

log = get_logger(__name__)


def compose_simple_node(state: PersonaRunState) -> dict:
    out_path = persona_run_dir(state) / "output.mp4"

    audio = None
    bg = None
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        audio = AudioFileClip(str(state["audio_path"]))
        bg = VideoFileClip(str(state["background_video_path"])).without_audio()
        bg = fit_vertical(bg)
        bg = loop_to_duration(bg, audio.duration)
        bg.with_audio(audio).write_videofile(str(out_path), **VIDEO_WRITE_KWARGS)
    except Exception as exc:
        log_exception(
            log,
            "simple_compose.failed",
            exc,
            background_video_path=state.get("background_video_path"),
            audio_path=state.get("audio_path"),
        )
        return {
            "is_fatal_error": True,
            "error_message": f"Simple composition failed: {describe_exception(exc)}",
        }
    finally:
        if bg is not None:
            bg.close()
        if audio is not None:
            audio.close()

    return {"output_video_path": str(out_path)}
