# Karaoke Caption Pipeline

`src/merge_captions.py` — word-level on-screen caption overlay burned into the output video.

---

## Pipeline

```
speech.wav
  → transcribe_and_align()   WhisperX: transcription + forced alignment → list[Word]
  → group_words()            group into 2-3 word Chunks
  → _build_caption_clips()   render PIL frames → list[ImageClip]
  → compose()                CompositeVideoClip(bg + captions) + audio → output.mp4
```

`align_node` runs steps 1–2 and stores `word_timings` in state. `compose_node` runs steps 3–4.

---

## Chunk grouping

A new chunk starts when any of these is true:

| Condition | Constant |
|---|---|
| word count would exceed limit | `MAX_WORDS_PER_CHUNK = 3` |
| joined char count would exceed limit | `MAX_CHARS_PER_CHUNK = 22` |
| silence gap before the word | `PAUSE_THRESHOLD_S = 0.3 s` |

The char limit is what keeps long words (e.g. German compounds) from overflowing the pill width at `FONT_SIZE = 90`.

---

## Rendering

Each caption frame is a full `1080×1920` RGBA image with a transparent background. MoviePy's `CompositeVideoClip` composites layers by alpha — the caption must match the video canvas size so it overlays at the correct absolute position.

**Base-once pattern** (`_build_caption_clips`): the shadow, pill, and all inactive-colour word labels are drawn once per chunk into a `base` image. Each per-word frame is `base.copy()` plus one overdraw of the active word in orange. This avoids redrawing identical geometry for every word in the chunk.

**Word timing**: the active highlight for word `i` runs from `word[i].start` to `word[i+1].start` (not `word[i].end`). Using the next word's start time rather than the current word's end means the highlight stays on during any micro-gap between words instead of briefly going dark.

**Inter-chunk gap**: if the silence between two chunks is shorter than `PAUSE_THRESHOLD_S`, the last chunk is shown all-inactive (no highlight) for the duration of the gap, giving a visual hold before the next chunk appears.

---

## Font

`_load_font` resolution order:

1. Explicit `font_path` argument (only used by `compose()` callers that pass it).
2. `src/assets/fonts/Anton-Regular.ttf` — the bundled font.
3. PIL's built-in default (no external dependency, but metrics will differ).

Anton-Regular must be present at the bundled path for production output. The PIL default fallback exists only so tests and dev runs don't crash when assets are absent.

---

## WhisperX model caching

`_whisper_asr` and `_whisper_align` are module-level singletons. The ASR model is loaded once on first call; alignment models are loaded once per detected language. This avoids multi-minute reload overhead when processing multiple personas in the same process.

`COMPUTE_DEVICE` (default `cpu`) and `WHISPER_MODEL` (default `base`) are read from `src/config.py`. Use `cuda` or `mps` for production throughput. `float16` compute is used on CUDA; `int8` elsewhere.

---

## Tuning

All visual constants are at the top of `merge_captions.py`:

| Constant | Default | Effect |
|---|---|---|
| `FONT_SIZE` | 90 | Pill height; reduce if long words overflow |
| `MAX_CHARS_PER_CHUNK` | 22 | Max joined chars before forced chunk break |
| `PAUSE_THRESHOLD_S` | 0.3 s | Silence that triggers a new chunk |
| `ACTIVE_COLOR` | `#F97316` orange | Highlighted word colour |
| `INACTIVE_COLOR` | `#9CA3AF` gray | Non-highlighted word colour |
| `pill_y` formula | `canvas_h * 0.70` | Vertical position of caption (70% from top) |
