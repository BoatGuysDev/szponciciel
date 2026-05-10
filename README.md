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
uv run python -m src.db.seed
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
