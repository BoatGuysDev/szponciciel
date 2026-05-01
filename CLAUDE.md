# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run all tests (requires RUN_MODE=test)
RUN_MODE=test uv run pytest

# Run a single test file
RUN_MODE=test uv run pytest src/tests/test_narrator_node.py

# Run a single test by name
RUN_MODE=test uv run pytest src/tests/test_narrator_node.py::TestNarratorNode::test_missing_run

# Apply DB migrations
uv run alembic upgrade head

# Seed the database (first run only)
uv run python -m src.db.seed
```

## Architecture

Szponciciel is a multi-agent LangGraph pipeline that autonomously generates and publishes TikTok news videos. The pipeline is: **News Fetcher → Writer ↔ Critic loop → Narrator → TTS → Video Assembly → Zernio upload**.

### Key data flow concepts

- A **Run** (`src/models/run.py`) represents one news story. It holds `base_script` (the approved script shared across all accounts) and the source article.
- A **Persona** (`src/models/persona.py`) represents one TikTok account with its own language, style, tone, voice settings (`voice_speaker` for named speaker or `voice_speaker_wav` for voice cloning), and `real_news_ratio`.
- A **PersonaRun** (`src/models/persona_run.py`) links a Run to a Persona — one video per persona per run.
- The shared **LangGraph state** is `PersonaRunState` (`src/nodes/state.py`): a `TypedDict` that flows through all nodes. Nodes signal failure by returning `{"is_fatal_error": True, "error_message": "..."}` rather than raising exceptions.

### Node pattern

Each node in `src/nodes/` accepts `PersonaRunState` and returns a partial state dict. Nodes are responsible for their own DB access via `Session(get_engine())`.

### Video providers

`src/providers/video_provider.py` defines the `VideoProvider` Protocol. `StockVideoProvider` and `AIVideoProvider` implement it. Video is generated once per Run (shared); audio/captions are per Persona.

### TTS

`tts_node` uses Coqui TTS (`xtts_v2` multilingual model). Set `COMPUTE_DEVICE=cuda` (or `mps`) for GPU acceleration; defaults to `cpu`. Output is written to `runs/{run_id}/{persona_id}/speech.wav`.

### Database

SQLite via SQLModel + Alembic. Dev DB file: `szponciciel.db`. Tests use an in-memory SQLite DB — tests **must** run with `RUN_MODE=test` or the base class raises immediately. `reset_db()` drops and recreates all tables before each test.

### LLM

Nodes use `ChatGoogleGenerativeAI` (Gemini). Auth via Google Application Default Credentials (`gcloud auth application-default login`). Model used: `gemini-2.5-flash-lite`.

## Testing

Tests live in `src/tests/`. Each node gets its own test file and class.

### Structure

- **`base_test_class.py`** — `BaseTestClass(ABC)`: enforces `RUN_MODE=test`, calls `reset_db()` before every test, and provides the `engine` fixture.
- **`test_{node_name}.py`** — one file per node; one class `Test{NodeName}(BaseTestClass)` per file.

### How to add tests for a new node

1. Create `src/tests/test_{node_name}.py`.
2. Subclass `BaseTestClass` and implement `create_graph()` as a pytest fixture that wires a minimal graph:

```python
@pytest.fixture(name="graph")
def create_graph(self) -> StateGraph:
    graph = StateGraph(state_schema=PersonaRunState)
    graph.add_node(my_node)
    graph.add_edge(START, "my_node")
    graph.add_edge("my_node", END)
    return graph
```

3. Invoke the graph in each test:

```python
result = graph.compile().invoke({"run_id": "1", ...})
```

4. Seed the DB when needed — use the `engine` fixture:

```python
def test_something(self, graph: StateGraph, engine: Engine):
    with Session(engine) as session:
        session.add(Run(status="pending", base_script="..."))
        session.commit()
```

5. Mock LLM / external calls by patching at the node's import path:

```python
with (
    patch("src.nodes.my_node.ChatGoogleGenerativeAI"),
    patch("src.nodes.my_node.create_agent", return_value=mock_agent),
):
    result = graph.compile().invoke({...})
```

### Assertions

| Scenario | Assertion |
|---|---|
| Fatal error | `assert result["is_fatal_error"]` and `result["error_message"] == "..."` |
| Success | `assert result.get("is_fatal_error") is None` and check expected state keys |

## Environment variables

| Variable | Purpose | Required |
|---|---|---|
| `DB_PATH` | Path to SQLite file (default: `szponciciel.db`) | Yes
| `RUN_MODE` | `test` → in-memory DB; omit for development | No (defaults to `development`) |
| `ZERNIO_API_KEY` | API key for Zernio upload | Yes
| `GOOGLE_GENAI_USE_VERTEXAI` | `true` / `false`for using Vertex AI | Yes
| `GOOGLE_CLOUD_PROJECT` | Google Cloud project ID | Yes
| `COMPUTE_DEVICE` | `cpu` / `cuda` / `mps` for Coqui TTS | No (defaults to `cpu`) |
