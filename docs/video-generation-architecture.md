# Video Generation Architecture

Covers PIAT-20 (Video Generation), PIAT-21 (Caption Generation), PIAT-22 (Audio Generation).

---

## Full Pipeline

```
ParentGraph (LangGraph StateGraph, SQLite checkpointing)
│
├── content_subgraph  [runs ONCE per pipeline execution]
│   Fetch news (Tavily) → Rank for virality → Writer loop → Approved script
│   ← interrupt_after: human approves script before production starts
│
└── production_subgraph  [sequential loop over active personas]
    For each persona:
      ├── decide_story_mode       (weighted random by fictional_news_ratio → "real_news"|"fictional_news")
      ├── choose_video_category   (LLM picks from 10 categories given article + persona stats)
      ├── narrator_node           (adapts script/article → persona style + language)
      ├── caption_node            (post caption + hashtags → TikTok text)
      ├── tts_node                (Coqui xTTSv2 → speech.wav)
      ├── [if show_captions=True]
      │   ├── align_node          (WhisperX → word timings)
      │   └── compose_node        (video_assembly_graph/transforms.py::compose → karaoke overlay)
      ├── [if show_captions=False]
      │   └── compose_simple_node (audio over video, no overlay)
      └── upload_node             (zernio_service::upload_tiktok_video)
```

### Writer loop
The writer-critic loop is a separate epic and treated as a black box here. The content subgraph
receives its approved script as output.

### Execution model
Personas are processed **sequentially** on a local Mac. Apple Silicon MPS can only run one
Coqui TTS / WhisperX job at a time — parallelism would be slower, not faster. Design as an
overnight batch job (~4-5 min per persona). When/if moved to cloud workers, swap the sequential
`for` loop for LangGraph's `Send` API.

---

## Graph State Schema

```python
class PipelineState(TypedDict):
    # Shared (content phase)
    run_id: str
    articles: list[NewsArticle]
    approved_script: str
    source_article: NewsArticle       # top-ranked real article

    # Persona loop control
    personas_queue: list[str]         # persona IDs remaining
    completed_personas: list[str]

class PersonaRunState(TypedDict):
    run_id: str
    persona_id: str
    story_mode: str                   # "real_news" | "fictional_news"
    narration: str
    tiktok_caption: str
    hashtags: list[str]
    audio_path: str                   # runs/{run_id}/{persona_id}/speech.wav
    video_category: str
    background_video_path: str
    output_video_path: str            # runs/{run_id}/{persona_id}/output.mp4
    zernio_post_id: str | None
```

---

## Persona Profile

Loaded from `personas.json` on first setup, persisted to SQLite.

```python
class Persona:
    id: str
    tiktok_account_id: str
    style: str                        # e.g. "sarcastic, fast-paced"
    tone: str                         # e.g. "skeptical"
    language: str                     # e.g. "pl", "en", "de"
    voice_speaker: str                # Coqui built-in speaker name
    voice_speaker_wav: str | None     # path to reference wav for voice cloning
    show_captions: bool               # if False, skip WhisperX + overlay
    fictional_news_ratio: float       # 0.0 = all real_news, 1.0 = all fictional_news
    is_active: bool
```

### Real vs fictional content decision
Each persona run draws a weighted random choice based on `fictional_news_ratio` (coin-toss style,
no historical correction). The selected `story_mode` is passed through generation so the writer,
critic, narrator, and caption nodes handle the current run as either grounded `real_news` or
confident in-universe `fictional_news`.

**Narrator node input:** `run.base_script` + persona `style`, `tone`, `language`. The narrator
adapts whatever script was produced — it does not distinguish between real and fake content.
The script is already the correct input (real article adapted upstream or fake script from the
writer loop). Translation and style adaptation happen in a single LLM call.

---

## VideoProvider Abstraction

```python
class VideoProvider(Protocol):
    def get_video(self, category: str) -> Path: ...

class StockVideoProvider:             # MVP — today
    root: Path                        # points to media/
    def get_video(self, category: str) -> Path:
        # random sample from media/{category}/

class AIVideoProvider:                # future — Kling, RunwayML, Pika, HeyGen
    def get_video(self, category: str, prompt: str) -> Path: ...
```

`video_strategy: "stock" | "ai"` is carried in graph state. Today it is always `"stock"`.

**Future evolution:** A `choose_video_strategy` node (LLM + per-category performance stats from
DB) sets `video_strategy` before `choose_video_category` runs. Graph topology is unchanged.

### Video categories (10 total)

| Category | Description |
|---|---|
| `satisfying` | AI slop satisfying content |
| `ugc` | Phone-recorded selfie-style videos |
| `subway` | Subway Surfers gameplay |
| `temple_run` | Temple Run gameplay |
| `minecraft` | Minecraft gameplay/speedrun |
| `fortnite` | Fortnite gameplay |
| `trackmania` | Trackmania racing |
| `space` | Space visuals / abstract space |
| `abstract` | Abstract visual content |

**Selection logic:** LLM receives the list of category names + article context + persona's
historical performance stats per category → picks one category → `StockVideoProvider` random-
samples a file from that folder.

**Future:** Agent uses `video_stats` table (views/likes per category per persona) to bias
selection toward historically better-performing categories.

---

## Database Schema (SQLite)

```sql
-- Loaded from personas.json on first setup
CREATE TABLE personas (
    id                  TEXT PRIMARY KEY,
    tiktok_account_id   TEXT NOT NULL,
    style               TEXT,
    tone                TEXT,
    language            TEXT,
    voice_speaker       TEXT,
    voice_speaker_wav   TEXT,           -- nullable, path to .wav for voice cloning
    show_captions       BOOLEAN DEFAULT TRUE,
    fictional_news_ratio REAL DEFAULT 0.5,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP
);

-- One row per pipeline execution (shared/content phase)
CREATE TABLE runs (
    id                  TEXT PRIMARY KEY,   -- UUID
    status              TEXT,               -- running | completed | failed
    source_article_url  TEXT,
    source_article_title TEXT,
    base_script         TEXT,               -- approved script from writer loop
    started_at          TIMESTAMP,
    completed_at        TIMESTAMP
);

-- One row per persona per run (production/fan-out phase)
CREATE TABLE persona_runs (
    id                  TEXT PRIMARY KEY,   -- UUID
    run_id              TEXT REFERENCES runs(id),
    persona_id          TEXT REFERENCES personas(id),
    status              TEXT,               -- pending | running | completed | failed
    story_mode          TEXT,               -- "real_news" | "fictional_news"
    narration           TEXT,
    tiktok_caption      TEXT,
    audio_path          TEXT,
    video_category      TEXT,
    background_video_path TEXT,
    output_video_path   TEXT,
    zernio_post_id      TEXT,               -- nullable, returned after upload
    error_message       TEXT,               -- nullable
    started_at          TIMESTAMP,
    completed_at        TIMESTAMP
);

-- Future: performance data fetched from Zernio analytics
-- Seam is zernio_post_id in persona_runs
-- CREATE TABLE video_stats (
--     id                  TEXT PRIMARY KEY,
--     persona_run_id      TEXT REFERENCES persona_runs(id),
--     fetched_at          TIMESTAMP,
--     views               INTEGER,
--     likes               INTEGER,
--     shares              INTEGER,
--     comments            INTEGER
-- );
```

---

## File Layout

```
media/
  satisfying/
  ugc/
  subway/
  temple_run/
  minecraft/
  fortnite/
  trackmania/
  space/
  abstract/

runs/
  {run_id}/
    {persona_id}/
      speech.wav
      output.mp4

src/
  config.py
  models/           — Run, Persona, PersonaRun (SQLModel)
  nodes/
    state.py        — PersonaRunState TypedDict
    caption_node/   — node.py, response_format.py, system_prompt.py
    narrator_node/  — node.py, system_prompt.py
    tts_node/       — node.py
  providers/        — VideoProvider protocol, StockVideoProvider, AIVideoProvider (stub)
  db/               — database.py, seed.py, seeds/
  tools/            — tiktok.py (upload_tiktok_video)
  tests/            — base_test_class.py, test_*.py

docs/               — architecture documentation
```

---

## LLM Nodes

All LLM-powered nodes use `gemini-2.5-flash-lite` via `ChatGoogleGenerativeAI` (Vertex AI free
tier). Auth via Google Application Default Credentials (`gcloud auth application-default login`).

| Node | Responsibility |
|---|---|
| Ranker | Score fetched articles for virality |
| Writer loop | Draft and refine fake news script (separate epic) |
| Narrator | Adapt script/article to persona style + language |
| Caption node | Generate TikTok post caption + hashtag list |
| Category selector | Pick video category from 10 options given article + stats |

TTS uses **Coqui xTTSv2 locally** (MPS on Apple Silicon). Coqui supports voice cloning 
via `speaker_wav` reference audio, enabling distinct
voices per persona.

---

## Caption Generation (PIAT-21)

Two separate caption concerns — do not conflate:

| Type | Description | Where generated |
|---|---|---|
| On-screen karaoke | Word-by-word pill overlay burned into video | `align_node` + `compose_node` (WhisperX + `transforms.py`) |
| TikTok post caption | Text description + hashtags submitted on upload | `caption_node` (LLM, runs after Narrator) |

`show_captions=False` on a persona skips `align_node` and `compose_node` entirely.
`caption_node` (post text + hashtags) always runs regardless of `show_captions`.

Hashtags are LLM-generated from the narration content. Trending hashtag API lookup is a future
enhancement.

---

## Established Patterns

1. **Nodes over tools for heavy work** — TTS, WhisperX, MoviePy are graph nodes (stateful,
   file-producing). LangChain `@tool` is reserved for LLM-callable side effects (upload,
   stats lookup).

2. **Seams over abstractions** — `VideoProvider` protocol costs nothing today; swapping
   `StockVideoProvider` for `AIVideoProvider` tomorrow costs nothing. Same pattern applies to
   TTS provider if Coqui is replaced later.

3. **State carries paths, not bytes** — intermediate files live on disk under `runs/`. Graph
   state carries string paths only. No in-memory blob passing between nodes.

4. **DB for everything persistent** — graph state is ephemeral per run. Personas, run history,
   and future stats live in SQLite. Loaded at node entry, never embedded in state.

5. **Weighted random for story mode** — `fictional_news_ratio` is a per-run coin toss, no
   historical correction for MVP. Simple, correct, trivially replaceable.

6. **Sequential fan-out for local Mac** — personas processed one at a time. MPS GPU is the
   bottleneck; parallelism would be slower. Migrate to `Send` API + cloud workers when needed.
