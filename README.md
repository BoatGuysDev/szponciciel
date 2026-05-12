# Szponciciel — TikTok AI News Agent

## Description

Szponciciel is a multi-agent content pipeline that autonomously fetches real news, generates TikTok-style video scripts (with a configurable fact/satire ratio), evaluates them in a Writer ↔ Critic loop, and publishes the final videos across a pool of TikTok accounts — each with its own persona, voice, and language.

The project is developed as a study project within the PIAT Jira space.

## Goal

Build a fully automated, self-improving TikTok content factory that:

- Discovers and ranks trending news articles
- Generates persona-specific scripts blending factual and satirical content (`real_news_ratio`)
- Refines scripts iteratively until a quality threshold is met
- Converts approved scripts into TikTok-ready videos (TTS narration + AI footage + captions)
- Publishes to multiple TikTok accounts via Zernio
- Collects performance metrics and feeds them back into the pipeline to optimize future content

## Setup

**Prerequisites:**
- Python 3.13+, [uv](https://docs.astral.sh/uv/)
- Google Cloud CLI, [gcloud](https://docs.cloud.google.com/sdk/docs/install-sdk)

```bash
# 1. Install dependencies
uv sync

# 2. Initialize Google Cloud CLI
gcloud init

# 3. Create local authentication credentials
gcloud auth application-default login

# 4. Configure environment
cp .env.example .env

# 5. Apply database migrations
uv run alembic upgrade head

# 6. Seed the database (first run only)
uv run python -m db.seed
```

**Additional guides:**
- [Configure application default credentials - Google Cloud CLI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/gcp-auth)

## Environment variables

Copy `.env.example` to `.env` and fill in the values. The variables:

| Variable | Purpose | Required | Default |
|---|---|---|---|
| `DB_PATH` | Path to the SQLite DB file | Yes | `szponciciel.db` |
| `RUN_MODE` | `development` for normal use; `test` switches to an in-memory DB and is required by the test suite | Yes | `development` |
| `ZERNIO_API_KEY` | API key for publishing videos via Zernio | Yes | — |
| `GROUND_TRUTH_MEDIA_ACCOUNT_ID` | TikTok account ID assigned to the ground-truth persona during DB seeding | Yes (for seeding) | — |
| `GOOGLE_GENAI_USE_VERTEXAI` | Route Gemini calls through Vertex AI (`true`) or the public GenAI API (`false`) | Yes | `true` |
| `GOOGLE_CLOUD_PROJECT` | Google Cloud project ID used for Vertex AI | Yes (when `GOOGLE_GENAI_USE_VERTEXAI=true`) | — |
| `COMPUTE_DEVICE` | Coqui TTS device: `cpu`, `cuda`, or `mps` | No | `cpu` |
| `TTS_MODEL` | Coqui TTS model name used by `tts_node` | No | `tts_models/multilingual/multi-dataset/xtts_v2` |

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
│   (Creator)     │  {persona, language, tone, real_news_ratio, voice}
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
│  real_news_ratio, content_tags, ...}    │
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
