# Szponciciel — TikTok AI News Agent

## Description

Szponciciel is a multi-agent content pipeline that autonomously fetches real news, generates TikTok-style video scripts with a per-run story mode, evaluates them in a Writer ↔ Critic loop, and publishes the final videos across a pool of TikTok accounts — each with its own persona, voice, and language.

The project is developed as a study project within the PIAT Jira space.

## Goal

Build a fully automated, self-improving TikTok content factory that:

- Discovers and ranks trending news articles
- Generates persona-specific scripts using a `story_mode` sampled from each persona's `fictional_news_ratio`
- Refines scripts iteratively until a quality threshold is met
- Converts approved scripts into TikTok-ready videos (TTS narration + AI footage + captions)
- Publishes to multiple TikTok accounts via Zernio
- Collects performance metrics and feeds them back into the pipeline to optimize future content

## Setup

**Prerequisites:**
- Python 3.13+, [uv](https://docs.astral.sh/uv/)
- FFmpeg, [installation guide](https://ffmpeg.org/download.html)
- Google Cloud CLI, [gcloud](https://docs.cloud.google.com/sdk/docs/install-sdk)

```bash
# 1. Install dependencies
uv sync

# 2. Install the pre-commit hook
uvx pre-commit install

# 3. Initialize Google Cloud CLI
gcloud init

# 4. Create local authentication credentials
gcloud auth application-default login

# 5. Configure environment
cp .env.example .env

# 6. Apply database migrations
uv run alembic upgrade head

# 7. Seed the database (first run only)
uv run python -m db.seed

# 8. Download background videos
uv run python scripts/download_videos.py
```

**Additional guides:**
- [Configure application default credentials - Google Cloud CLI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/gcp-auth)

## Environment variables

Copy `.env.example` to `.env` and fill in the values. The variables:

| Variable | Purpose | Required | Default |
|---|---|---|---|
| `DATABASE_URL` | Full SQLAlchemy URL. Required (no implicit default). Test runs are pinned to `sqlite:///:memory:` by `src/tests/conftest.py` regardless of this value | Yes | — |
| `RUN_MODE` | Application mode flag for non-DB behaviours. Valid values: `development`, `test`, `production` | No | `development` |
| `LOG_LEVEL` | Logging level for live console logs: `DEBUG`, `INFO`, `WARNING`, `ERROR` | No | `INFO` |
| `LOG_FILE` | JSONL file path for completed pipeline run artifacts. Each line is one wide structured event for a whole run | No | `runs/logs/pipeline.jsonl` |
| `COMPUTE_DEVICE` | Coqui TTS + WhisperX device: `cpu`, `cuda`, or `mps` | No | `cpu` |
| `WHISPER_MODEL` | WhisperX model size for `align_node`: `tiny`, `base`, `small`, `medium`, `large-v3` | No | `base` |
| `TTS_MODEL` | Coqui TTS model name used by `tts_node` | No | `tts_models/multilingual/multi-dataset/xtts_v2` |
| `MODEL` | Gemini model used by LLM nodes | No | `gemini-2.5-flash-lite` |
| `GOOGLE_CLOUD_PROJECT` | Google Cloud project ID used for Vertex AI | Yes (when `GOOGLE_GENAI_USE_VERTEXAI=true`) | — |
| `GOOGLE_GENAI_USE_VERTEXAI` | Route Gemini calls through Vertex AI (`true`) or the public GenAI API (`false`) | Yes | `true` |
| `LANGSMITH_TRACING` | Enable LangSmith tracing of every run (`true`/`false`) | No | `false` |
| `LANGSMITH_ENDPOINT` | LangSmith API endpoint URL | No | `https://api.smith.langchain.com` |
| `LANGSMITH_API_KEY` | LangSmith API key (from https://smith.langchain.com) | When tracing | — |
| `LANGSMITH_PROJECT` | LangSmith project to log traces under | No | `default` |
| `ZERNIO_API_KEY` | API key for publishing videos via Zernio | Yes | — |
| `TAVILY_API_KEY` | API key for article content fetching via Tavily | Yes | — |
| `GROUND_TRUTH_MEDIA_ACCOUNT_ID` | TikTok account ID assigned to the ground-truth persona during DB seeding | Yes (for seeding) | — |
| `MEDIA_ROOT` | Media root directory for stock video assets | No | `media` |
| `WRITER_CRITIC_MAX_ITERS` | Maximum writer↔critic loop iterations | No | `3` |
| `MAX_SCRIPT_LENGTH` | Maximum character length for generated TikTok scripts | No | `8000` |

## Running the pipeline

The whole pipeline is a single LangGraph orchestrator — **intake → research → run_personas → finalize**. One run picks a news story, then generates and uploads one video per active persona. Complete [Setup](#setup) first (credentials, migrations, seed, background videos), since a real run calls Gemini, Tavily, Coqui TTS, and Zernio.

### CLI (direct / cron)

```bash
# Targeted topic
uv run python -m orchestrator "post videos about the USA-Iran conflict"

# Generic — researcher sweeps the default news categories
uv run python -m orchestrator "research and post a few videos"
```

The prompt argument is **required** (running with no argument prints usage). A cron job runs the same command with a generic prompt.

### Web UI (LangGraph Studio)

```bash
uv run langgraph dev
```

This serves the graph at `http://127.0.0.1:2024` and prints a Studio URL:
`https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`. Open it, submit `{ "prompt": "..." }`, and watch the run live.

Local runs print readable logs to stdout as the pipeline executes. At finalize time, the app appends one structured JSON object per run to `runs/logs/pipeline.jsonl`, including node timings, agent calls, tool calls, inputs, outputs, outcomes, and errors.

> **"Failed to fetch" / "Failed to initialize Studio" while the server is running?** The browser is blocking an HTTPS Studio page from calling `http://localhost`. Use Chrome (it allows localhost), or run `uv run langgraph dev --tunnel` to expose an HTTPS endpoint Studio can reach.

### Tracing (LangSmith)

For full LLM tracing, token/cost tracking, and replay of failed runs, set in `.env`:

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<key from https://smith.langchain.com>
LANGSMITH_PROJECT=szponciciel
```

Every run is then traced in LangSmith with no code changes. Each persona's pipeline is logged as a `persona:<id>` run tagged with `run_id` and `persona_id`, so you can filter and replay individual failures. Left off (the default), tracing adds no overhead.

## Agent Workflow

```
┌─────────────────┐
│  News Fetcher   │  Fetches, scrapes, deduplicates, and virality-scores articles
│  (Researcher)   │  Tools: Tavily / Brave Search API + RSS feeds
└────────┬────────┘
         │ ranked article candidates
         ▼
┌─────────────────┐
│     Writer      │  Generates a script per account, parameterized by
│   (Creator)     │  {persona, language, tone, fictional_news_ratio, voice}
└────────┬────────┘
         │ draft script
         ▼
┌─────────────────┐
│     Critic      │◄─── rewrites until threshold met or iteration cap hit
│                 │
└────────┬────────┘
         │ approved script
         ▼
┌─────────────────────────────────────────┐
│         Video Content Creator           │
│  TTS (per account voice)                │
│  Video generation (shared per story)    │
│  Caption + hashtag generation           │
└────────────────────┬────────────────────┘
                     │ video package
                     ▼
┌─────────────────────────────────────────┐
│        Output & Distribution            │
│  Upload via Zernio API                  │
│  Attach run metadata {run_id, persona,  │
│  fictional_news_ratio, story_mode, ...} │
└─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│       Metrics Collection (future)       │
│  TikTok API: views, likes, completion   │
│  Joined on run_id → priors store        │
│  Feeds back into Writer & Critic tuning │
└─────────────────────────────────────────┘
```

Each account runs its own Writer ↔ Critic loop with its own path config. Video footage is generated once per news story and shared; narration and captions are generated per account.


## Results

| Name | Status | Description |
|---|---|---|
| **PIAT-1 — Project Foundation** | Done | All setup and groundwork tasks before development begins. Includes board configuration, workflow graph, framework research, and agent documentation. |
| **PIAT-2 — News Fetcher Agent** | To Do | Fetches, preprocesses, and tags real news as the pipeline entry point. Uses Tavily as the primary tool; handles deduplication, virality pre-scoring, and output schema normalization. |
| **PIAT-3 — Content Creator Agent** | To Do | Generates a per-account TikTok script parameterized by persona, language, tone, `true_fake_ratio`, and voice. Handles Critic feedback within the refinement loop. |
| **PIAT-4 — Critic Agent** | To Do | Evaluates generated scripts for TikTok catchiness. Defines scoring criteria, exit thresholds, and structured feedback format sent back to the Content Creator. |
| **PIAT-5 — Creator ↔ Critic Loop Orchestration** | To Do | Orchestrates the per-account script generation loop using LangGraph. Assigns `run_id`, stores full path metadata per run, and exits on approval or iteration cap. |
| **PIAT-6 — Narrator & Video Generation** | To Do | Converts approved scripts into TikTok-ready videos. Video footage is generated once per story; TTS narration and captions are generated per account and assembled into one video file each. |
| **PIAT-7 — End-to-End Pipeline Orchestration** | To Do | Wires all agents into a functioning pipeline. Covers error handling, retry logic, observability, configuration management, and integration tests. |
| **PIAT-8 — Output & Distribution** | To Do | Publishes generated videos to the TikTok account pool via Zernio with full path metadata attached, scheduling posts to avoid spam-pattern detection. |
| **PIAT-23 — Metrics Collection & Path Analysis** | To Do | Collects TikTok performance metrics (views, likes, completion rate) per post and joins them on `run_id` to build a priors store for the Adaptive Pipeline. |
| **PIAT-27 — Adaptive Pipeline** | To Do | Extends MVP agents to consume historical performance data from the priors store, biasing script ratios, Critic thresholds, and virality scoring toward what works. |
