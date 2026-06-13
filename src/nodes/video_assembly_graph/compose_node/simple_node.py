from moviepy import AudioFileClip, VideoFileClip

from nodes.state import PersonaRunState, persona_run_dir
from nodes.video_assembly_graph.transforms import (
    VIDEO_WRITE_KWARGS,
    fit_vertical,
    loop_to_duration,
)


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
    finally:
        if bg is not None:
            bg.close()
        if audio is not None:
            audio.close()

    return {"output_video_path": str(out_path)}
