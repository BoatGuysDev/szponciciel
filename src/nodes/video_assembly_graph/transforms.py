from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import PROJECT_ROOT


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Chunk:
    words: tuple[Word, ...]

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end


_whisper_asr: object | None = None
_whisper_align: dict[str, tuple] = {}  # lang -> (align_model, metadata)


def transcribe_and_align(audio_path: Path, *, device: str, model_size: str) -> list[Word]:
    import whisperx

    global _whisper_asr

    compute_type = "float16" if device == "cuda" else "int8"
    audio = whisperx.load_audio(str(audio_path))

    if _whisper_asr is None:
        _whisper_asr = whisperx.load_model(model_size, device, compute_type=compute_type)
    result = _whisper_asr.transcribe(audio, batch_size=16)

    lang = result.get("language", "en")
    if lang not in _whisper_align:
        _whisper_align[lang] = whisperx.load_align_model(language_code=lang, device=device)
    align_model, metadata = _whisper_align[lang]
    result = whisperx.align(result["segments"], align_model, metadata, audio, device)

    words = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            if "start" in w and "end" in w and w.get("word", "").strip():
                words.append(Word(text=w["word"].strip(), start=w["start"], end=w["end"]))
    return words


MAX_WORDS_PER_CHUNK = 3
MAX_CHARS_PER_CHUNK = 22
PAUSE_THRESHOLD_S = 0.3


def group_words(words: list[Word]) -> list[Chunk]:
    if not words:
        return []

    chunks: list[Chunk] = []
    current: list[Word] = [words[0]]
    current_chars = len(words[0].text)

    for w in words[1:]:
        gap = w.start - current[-1].end
        char_count = current_chars + 1 + len(w.text)
        at_limit = len(current) >= MAX_WORDS_PER_CHUNK
        too_long = char_count > MAX_CHARS_PER_CHUNK
        pause = gap > PAUSE_THRESHOLD_S

        if at_limit or too_long or pause:
            chunks.append(Chunk(words=tuple(current)))
            current = [w]
            current_chars = len(w.text)
        else:
            current.append(w)
            current_chars = char_count

    if current:
        chunks.append(Chunk(words=tuple(current)))
    return chunks


FONT_SIZE = 65
TEXT_COLOR = (255, 255, 255, 255)
SHADOW_OFFSET_X = 4
SHADOW_OFFSET_Y = 5
SHADOW_BLUR = 4
SHADOW_OPACITY = 210
CAPTION_Y_RATIO = 0.75
SLIDE_IN_DURATION = 0.15  # seconds
SLIDE_IN_DISTANCE = 35  # pixels

TARGET_W = 1080
TARGET_H = 1920

VIDEO_WRITE_KWARGS: dict = {
    "codec": "libx264",
    "audio_codec": "aac",
    "fps": 30,
    "preset": "medium",
    "threads": 4,
}


BUNDLED_FONT_PATH = PROJECT_ROOT / "src" / "assets" / "fonts" / "Anton-Regular.ttf"
_SYSTEM_FONT_FALLBACKS = [
    "/System/Library/Fonts/Supplemental/Impact.ttf",  # macOS
    "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",  # Linux
    "/Windows/Fonts/impact.ttf",  # Windows
]


def _load_font(font_path: str | None) -> ImageFont.FreeTypeFont:
    if font_path and Path(font_path).is_file():
        return ImageFont.truetype(font_path, FONT_SIZE)
    if BUNDLED_FONT_PATH.is_file():
        return ImageFont.truetype(str(BUNDLED_FONT_PATH), FONT_SIZE)
    for p in _SYSTEM_FONT_FALLBACKS:
        if Path(p).is_file():
            return ImageFont.truetype(p, FONT_SIZE)
    raise FileNotFoundError(f"No caption font found. Add Anton-Regular.ttf to {BUNDLED_FONT_PATH}.")


def render_text(text: str, font: ImageFont.FreeTypeFont) -> tuple[np.ndarray, int, int]:
    """Render text with blurred drop shadow on a transparent canvas.

    Returns (RGBA array, left_pad, top_pad) so the caller can compute where
    the visual text starts within the returned frame.
    """
    bb = font.getbbox(text)
    text_w, text_h = bb[2] - bb[0], bb[3] - bb[1]

    left_pad = SHADOW_BLUR
    top_pad = SHADOW_BLUR
    right_pad = SHADOW_OFFSET_X + SHADOW_BLUR
    bottom_pad = SHADOW_OFFSET_Y + SHADOW_BLUR

    canvas_w = text_w + left_pad + right_pad
    canvas_h = text_h + top_pad + bottom_pad
    tx, ty = left_pad - bb[0], top_pad - bb[1]

    shadow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text(
        (tx + SHADOW_OFFSET_X, ty + SHADOW_OFFSET_Y),
        text,
        font=font,
        fill=(0, 0, 0, SHADOW_OPACITY),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(SHADOW_BLUR))

    img = shadow.copy()
    ImageDraw.Draw(img).text((tx, ty), text, font=font, fill=TEXT_COLOR)

    return np.array(img), left_pad, top_pad


def _make_slide_in(base_x: int, base_y: int, slide_dur: float):
    def pos(t: float) -> tuple[int, int]:
        if slide_dur <= 0 or t >= slide_dur:
            return (base_x, base_y)
        # ease-out quad: fast start, decelerates into final position
        progress = 1.0 - (1.0 - t / slide_dur) ** 2
        return (base_x, base_y + int(SLIDE_IN_DISTANCE * (1.0 - progress)))

    return pos


def _build_caption_clips(chunks: list[Chunk], font: ImageFont.FreeTypeFont) -> list:
    from moviepy import ImageClip

    clips = []
    for chunk in chunks:
        text = " ".join(w.text.upper() for w in chunk.words)
        frame, left_pad, top_pad = render_text(text, font)

        bb = font.getbbox(text)
        text_w = bb[2] - bb[0]
        base_x = (TARGET_W - text_w) // 2 - left_pad
        base_y = int(TARGET_H * CAPTION_Y_RATIO) - top_pad

        dur = max(chunk.end - chunk.start, 0.05)
        slide_dur = min(SLIDE_IN_DURATION, dur)

        clips.append(
            ImageClip(frame)
            .with_start(chunk.start)
            .with_duration(dur)
            .with_position(_make_slide_in(base_x, base_y, slide_dur))
        )

    return clips


def fit_vertical(clip):
    from moviepy.video.fx import Crop, Resize

    target_aspect = TARGET_W / TARGET_H
    clip_aspect = clip.w / clip.h

    if clip_aspect > target_aspect:
        scale = TARGET_H / clip.h
        resized = clip.with_effects([Resize(new_size=(int(clip.w * scale), TARGET_H))])
        x_center = resized.w / 2
        return resized.with_effects(
            [
                Crop(
                    x1=x_center - TARGET_W / 2,
                    x2=x_center + TARGET_W / 2,
                    y1=0,
                    y2=TARGET_H,
                )
            ]
        )

    scale = TARGET_W / clip.w
    resized = clip.with_effects([Resize(new_size=(TARGET_W, int(clip.h * scale)))])
    y_center = resized.h / 2
    return resized.with_effects(
        [
            Crop(
                x1=0,
                x2=TARGET_W,
                y1=y_center - TARGET_H / 2,
                y2=y_center + TARGET_H / 2,
            )
        ]
    )


def loop_to_duration(clip, duration: float):
    from moviepy.video.compositing.CompositeVideoClip import concatenate_videoclips

    if clip.duration <= 0:
        raise ValueError(f"clip.duration must be positive, got {clip.duration}")
    if clip.duration >= duration:
        return clip.subclipped(0, duration)

    loops = []
    remaining = duration
    while remaining > 0:
        take = min(clip.duration, remaining)
        loops.append(clip.subclipped(0, take))
        remaining -= take
    return concatenate_videoclips(loops)


def compose(
    video_path: Path,
    audio_path: Path,
    words: list[Word],
    out_path: Path,
    font_path: str | None = None,
) -> Path:
    from moviepy import AudioFileClip, CompositeVideoClip, VideoFileClip

    font = _load_font(font_path)
    chunks = group_words(words)
    audio = None
    bg = None
    final = None
    try:
        audio = AudioFileClip(str(audio_path))
        bg = VideoFileClip(str(video_path)).without_audio()
        bg = fit_vertical(bg)
        bg = loop_to_duration(bg, audio.duration)
        final = CompositeVideoClip([bg, *_build_caption_clips(chunks, font)], size=(TARGET_W, TARGET_H))
        final = final.with_duration(audio.duration).with_audio(audio)
        final.write_videofile(str(out_path), **VIDEO_WRITE_KWARGS)
    finally:
        if final is not None:
            final.close()
        if bg is not None:
            bg.close()
        if audio is not None:
            audio.close()

    return out_path
