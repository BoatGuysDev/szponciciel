from pathlib import Path

from merge_captions import Word, compose

from nodes.state import PersonaRunState, persona_run_dir


def compose_node(state: PersonaRunState) -> dict:
    out_path = persona_run_dir(state) / "output.mp4"

    words = [
        Word(text=w["text"], start=w["start"], end=w["end"])
        for w in state["word_timings"]
    ]

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        compose(
            Path(state["background_video_path"]),
            Path(state["audio_path"]),
            words,
            out_path,
        )
    except Exception as e:
        return {
            "is_fatal_error": True,
            "error_message": f"Video composition failed: {e}",
        }

    return {"output_video_path": str(out_path)}
