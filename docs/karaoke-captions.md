# Karaoke Caption Pipeline

`src/merge_captions.py` — word-level on-screen caption overlay burned into the output video.

---

## Pipeline

```text
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

The char limit prevents long words from overflowing the visible width at `FONT_SIZE = 65`.

---

## Rendering

Each chunk is rendered into a **minimal transparent canvas** (just large enough to hold the text + shadow padding). MoviePy's `CompositeVideoClip` composites it over the video by alpha, positioned absolutely so it lands in the correct place.

**Visual style**: all-caps white text, no background pill, blurred bottom-right drop shadow (`SHADOW_OFFSET_X/Y`, `SHADOW_BLUR`). One `ImageClip` per chunk — no per-word colour changes.

**Shadow technique**: draw the shadow text offset by `(SHADOW_OFFSET_X, SHADOW_OFFSET_Y)` on a transparent canvas, apply `GaussianBlur(SHADOW_BLUR)`, then overdraw the main text at the origin position.

**Slide-in animation**: each clip uses a position callable (`_make_slide_in`) that starts `SLIDE_IN_DISTANCE` pixels below the target `y` and eases out (quadratic) over `SLIDE_IN_DURATION` seconds. The clip disappears instantly at its end — no fade-out.

---

## Font

`_load_font` resolution order:

1. Explicit `font_path` argument (only used by `compose()` callers that pass it).
2. `src/assets/fonts/Anton-Regular.ttf` — the bundled font (Anton, Google Fonts, bold condensed).
3. System Impact: macOS `/System/Library/Fonts/Supplemental/Impact.ttf`, Linux msttcorefonts, Windows `C:/Windows/Fonts/impact.ttf`.
4. `FileNotFoundError` — crashes rather than silently using PIL's bitmap default (which produces unreadable output).

Anton-Regular.ttf must be present at the bundled path for production output.

---

## WhisperX model caching

`_whisper_asr` and `_whisper_align` are module-level singletons. The ASR model is loaded once on first call; alignment models are loaded once per detected language. This avoids multi-minute reload overhead when processing multiple personas in the same process.

`COMPUTE_DEVICE` (default `cpu`) and `WHISPER_MODEL` (default `base`) are read from `src/config.py`. Use `cuda` or `mps` for production throughput. `float16` compute is used on CUDA; `int8` elsewhere.

---

## Tuning

All visual constants are at the top of `merge_captions.py`:

| Constant | Default | Effect |
|---|---|---|
| `FONT_SIZE` | 65 | Caption text size |
| `MAX_CHARS_PER_CHUNK` | 22 | Max joined chars before forced chunk break |
| `PAUSE_THRESHOLD_S` | 0.3 s | Silence that triggers a new chunk |
| `CAPTION_Y_RATIO` | 0.75 | Vertical position (75% from top) |
| `SHADOW_OFFSET_X/Y` | 4, 5 | Drop shadow offset |
| `SHADOW_BLUR` | 4 | GaussianBlur radius for shadow softness |
| `SHADOW_OPACITY` | 210 | Shadow alpha (0–255) |
| `SLIDE_IN_DURATION` | 0.15 s | Ease-out animation duration on enter |
| `SLIDE_IN_DISTANCE` | 35 px | Starting offset below final position |
