from pathlib import Path

from moviepy import AudioFileClip, VideoFileClip

from merge_captions import VIDEO_WRITE_KWARGS, fit_vertical, loop_to_duration

from nodes.state import PersonaRunState


def compose_simple_node(state: PersonaRunState) -> dict:
    """Merges audio over background video with no caption overlay and writes output.mp4."""
    out_path = Path(f"runs/{state['run_id']}/{state['persona_id']}/output.mp4")

    audio = None
    bg = None
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        audio = AudioFileClip(str(state["audio_path"]))
        bg = VideoFileClip(str(state["background_video_path"])).without_audio()
        bg = fit_vertical(bg)
        bg = loop_to_duration(bg, audio.duration)
        bg.with_audio(audio).write_videofile(str(out_path), **VIDEO_WRITE_KWARGS)
    except Exception as e:
        return {
            "is_fatal_error": True,
            "error_message": f"Simple composition failed: {e}",
        }
    finally:
        if bg is not None:
            bg.close()
        if audio is not None:
            audio.close()

    return {"output_video_path": str(out_path)}
