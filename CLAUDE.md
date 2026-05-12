## Commands

```bash
# Tests require RUN_MODE=test (BaseTestClass raises otherwise)
RUN_MODE=test uv run pytest

# Apply DB migrations
uv run alembic upgrade head

# Seed the database (first run only)
uv run python -m db.seed
```

## Architecture

Szponciciel is a multi-agent LangGraph pipeline that autonomously generates and publishes TikTok news videos. The pipeline is: **News Fetcher → Writer ↔ Critic loop → Narrator → TTS → Video Assembly → Zernio upload**.

### Key data flow concepts

- A **Run** (`src/models/run.py`) represents one news story. It holds `base_script` (the approved script shared across all accounts) and the source article.
- A **Persona** (`src/models/persona.py`) represents one TikTok account with its own language, style, tone, voice settings (`voice_speaker` for named speaker or `voice_speaker_wav` for voice cloning), and `real_news_ratio`.
- A **PersonaRun** (`src/models/persona_run.py`) links a Run to a Persona — one video per persona per run.
- The shared **LangGraph state** is `PersonaRunState` (`src/nodes/state.py`): a `TypedDict` that flows through all nodes. Nodes signal failure by returning `{"is_fatal_error": True, "error_message": "..."}` rather than raising exceptions.

### Node pattern

Each node in `src/nodes/` accepts `PersonaRunState` and returns a partial state dict. Nodes open their own DB sessions via `Session(get_engine())`.

### Video providers

`src/providers/video_provider.py` defines the `VideoProvider` Protocol. `StockVideoProvider` and `AIVideoProvider` implement it. Video is generated once per Run (shared); audio/captions are per Persona.

### TTS

`tts_node` uses Coqui TTS (`xtts_v2` multilingual model). Set `COMPUTE_DEVICE=cuda` (or `mps`) for GPU acceleration; defaults to `cpu`. `WHISPER_MODEL` sets the WhisperX model size for `align_node`; defaults to `base`. See `docs/karaoke-captions.md` for the full caption pipeline (chunk grouping, rendering, timing model).

### Database

SQLite via SQLModel + Alembic. Dev DB file: `szponciciel.db`. Tests use an in-memory SQLite DB — tests **must** run with `RUN_MODE=test` or the base class raises immediately. `reset_db()` drops and recreates all tables before each test.

### LLM

Nodes use `ChatGoogleGenerativeAI` (Gemini, `gemini-2.5-flash-lite`). Auth via Google Application Default Credentials (`gcloud auth application-default login`).

## Testing

Tests live in `src/tests/`. Conventions:

- **`base_test_class.py`** — `BaseTestClass(ABC)`: enforces `RUN_MODE=test`, calls `reset_db()` before every test, and provides the `engine` fixture.
- **`test_{node_name}.py`** — one file per node; one class `Test{NodeName}(BaseTestClass)` per file. Each class provides a `graph` pytest fixture that wires a minimal `StateGraph` with just the node under test (START → node → END). Patch LLM/external calls at the node's import path. See existing test files for the exact shape.
