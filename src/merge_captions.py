from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Chunk:
    """A group of 2-3 words displayed together."""

    words: tuple[Word, ...]

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end


_whisper_asr: object | None = None
_whisper_align: dict = {}  # lang -> (align_model, metadata)


def transcribe_and_align(
    audio_path: Path, *, device: str, model_size: str
) -> list[Word]:
    """Run WhisperX transcription + forced alignment, return word timings."""
    import whisperx

    global _whisper_asr

    compute_type = "float16" if device == "cuda" else "int8"
    audio = whisperx.load_audio(str(audio_path))

    if _whisper_asr is None:
        _whisper_asr = whisperx.load_model(
            model_size, device, compute_type=compute_type
        )
    result = _whisper_asr.transcribe(audio, batch_size=16)

    lang = result.get("language", "en")
    if lang not in _whisper_align:
        _whisper_align[lang] = whisperx.load_align_model(
            language_code=lang, device=device
        )
    align_model, metadata = _whisper_align[lang]
    result = whisperx.align(result["segments"], align_model, metadata, audio, device)

    words = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            if "start" in w and "end" in w and w.get("word", "").strip():
                words.append(
                    Word(text=w["word"].strip(), start=w["start"], end=w["end"])
                )
    return words


MAX_WORDS_PER_CHUNK = 3
MAX_CHARS_PER_CHUNK = 22
PAUSE_THRESHOLD_S = 0.3


def group_words(words: list[Word]) -> list[Chunk]:
    if not words:
        return []

    chunks: list[Chunk] = []
    current: list[Word] = [words[0]]

    for w in words[1:]:
        gap = w.start - current[-1].end
        char_count = (
            sum(len(x.text) for x in current) + len(current) - 1 + 1 + len(w.text)
        )
        at_limit = len(current) >= MAX_WORDS_PER_CHUNK
        too_long = char_count > MAX_CHARS_PER_CHUNK
        pause = gap > PAUSE_THRESHOLD_S

        if at_limit or too_long or pause:
            chunks.append(Chunk(words=tuple(current)))
            current = [w]
        else:
            current.append(w)

    if current:
        chunks.append(Chunk(words=tuple(current)))
    return chunks


FONT_SIZE = 90
PILL_PAD_H = 30
PILL_PAD_V = 14
PILL_RADIUS = 16
WORD_GAP = 18
ACTIVE_COLOR = (249, 115, 22, 255)  # #F97316 orange
INACTIVE_COLOR = (156, 163, 175, 255)  # #9CA3AF gray
PILL_COLOR = (255, 255, 255, 230)
SHADOW_OFFSET = 3
SHADOW_COLOR = (0, 0, 0, 38)

TARGET_W = 1080
TARGET_H = 1920

VIDEO_WRITE_KWARGS: dict = {
    "codec": "libx264",
    "audio_codec": "aac",
    "fps": 30,
    "preset": "medium",
    "threads": 4,
}


def _load_font(font_path: str | None) -> ImageFont.FreeTypeFont:
    if font_path and Path(font_path).is_file():
        return ImageFont.truetype(font_path, FONT_SIZE)
    bundled = Path(__file__).resolve().parent / "assets/fonts/Anton-Regular.ttf"
    if bundled.is_file():
        return ImageFont.truetype(str(bundled), FONT_SIZE)
    return ImageFont.load_default(FONT_SIZE)


def render_pill(
    chunk: Chunk,
    active_idx: int,
    font: ImageFont.FreeTypeFont,
    canvas_w: int,
    canvas_h: int,
) -> np.ndarray:
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    word_texts = [w.text.upper() for w in chunk.words]
    bboxes = [font.getbbox(t) for t in word_texts]
    word_widths = [bb[2] - bb[0] for bb in bboxes]
    word_heights = [bb[3] - bb[1] for bb in bboxes]
    total_text_w = sum(word_widths) + WORD_GAP * (len(word_texts) - 1)
    max_text_h = max(word_heights)

    pill_w = total_text_w + 2 * PILL_PAD_H
    pill_h = max_text_h + 2 * PILL_PAD_V
    pill_x = (canvas_w - pill_w) // 2
    pill_y = int(canvas_h * 0.70) - pill_h // 2

    draw.rounded_rectangle(
        [
            pill_x + SHADOW_OFFSET,
            pill_y + SHADOW_OFFSET,
            pill_x + pill_w + SHADOW_OFFSET,
            pill_y + pill_h + SHADOW_OFFSET,
        ],
        radius=PILL_RADIUS,
        fill=SHADOW_COLOR,
    )
    draw.rounded_rectangle(
        [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
        radius=PILL_RADIUS,
        fill=PILL_COLOR,
    )

    x_cursor = pill_x + PILL_PAD_H
    text_y = pill_y + PILL_PAD_V
    for i, (text, bb) in enumerate(zip(word_texts, bboxes)):
        color = ACTIVE_COLOR if i == active_idx else INACTIVE_COLOR
        draw.text((x_cursor - bb[0], text_y - bb[1]), text, font=font, fill=color)
        x_cursor += (bb[2] - bb[0]) + WORD_GAP

    return np.array(img)


def fit_vertical(clip):
    """Crop/resize clip to fill 1080×1920."""
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

    if clip.duration >= duration:
        return clip.subclipped(0, duration)

    loops = []
    remaining = duration
    while remaining > 0:
        take = min(clip.duration, remaining)
        loops.append(clip.subclipped(0, take))
        remaining -= take
    return concatenate_videoclips(loops)


def _build_caption_clips(chunks: list[Chunk], font: ImageFont.FreeTypeFont) -> list:
    from moviepy import ImageClip

    clips = []
    for chunk_idx, chunk in enumerate(chunks):
        for word_idx, word in enumerate(chunk.words):
            frame = render_pill(chunk, word_idx, font, TARGET_W, TARGET_H)
            end_time = (
                chunk.words[word_idx + 1].start
                if word_idx < len(chunk.words) - 1
                else word.end
            )
            dur = max(end_time - word.start, 0.05)
            clips.append(
                ImageClip(frame)
                .with_start(word.start)
                .with_duration(dur)
                .with_position((0, 0))
            )

        if chunk_idx < len(chunks) - 1:
            next_chunk = chunks[chunk_idx + 1]
            gap = next_chunk.start - chunk.end
            if 0 < gap < PAUSE_THRESHOLD_S:
                frame = render_pill(chunk, -1, font, TARGET_W, TARGET_H)
                clips.append(
                    ImageClip(frame)
                    .with_start(chunk.end)
                    .with_duration(gap)
                    .with_position((0, 0))
                )

    return clips


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
    audio = AudioFileClip(str(audio_path))
    bg = VideoFileClip(str(video_path)).without_audio()
    try:
        bg = fit_vertical(bg)
        bg = loop_to_duration(bg, audio.duration)
        final = CompositeVideoClip(
            [bg, *_build_caption_clips(chunks, font)], size=(TARGET_W, TARGET_H)
        )
        final = final.with_duration(audio.duration).with_audio(audio)
        final.write_videofile(str(out_path), **VIDEO_WRITE_KWARGS)
    finally:
        bg.close()
        audio.close()

    return out_path
