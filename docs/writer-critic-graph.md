# Writer ↔ Critic Subgraph

`writer_critic_graph` (`src/nodes/writer_critic_graph/graph.py`) is a top-level node in `PersonaRunState` that internally runs a separate LangGraph subgraph over `WriterCriticState`.

## Two-level state pattern

The outer function accepts `PersonaRunState`, loads `Run` and `Persona` from the DB, builds the internal graph, invokes it with a fresh `WriterCriticState`, then writes the approved `draft_script` back to `Run.base_script` before returning to `PersonaRunState`.

The inner nodes (`writer_node`, `critic_node`) only see `WriterCriticState` — they have no access to `PersonaRunState`.

## Loop routing

After `writer_node`, `_writer_router` exits immediately to `END` if `is_fatal_error` is set, skipping the critic entirely.

After each `critic_node` pass, `_critic_router` exits to `END` if any of these hold:

- `is_fatal_error` is set
- `iterations == settings.writer_critic_max_iters` (`WRITER_CRITIC_MAX_ITERS`, default 3)
- `reliability_score >= settings.script_reliability_threshold` (`SCRIPT_RELIABILITY_THRESHOLD`, default 0.8)

Otherwise routes back to `writer_node`.

`reliability_score` is the arithmetic mean of the four critic scores: `coherence_score`, `grammar_score`, `unambiguity_score`, `catchiness_score` (each 0.0–1.0).

## Writer node

On the first iteration (`review` is `None`), `writer_node` calls `fetch_article_content(url)` via Tavily (`TavilyExtract`) to retrieve the article body. On revisions it works solely from the existing `draft_script` and `review.corrections` — no re-fetch.

Output is truncated to `settings.max_script_length` (`MAX_SCRIPT_LENGTH`, default 8000 chars).

## Critic node

Scores the draft on four rubrics and returns concrete `corrections`. Returns an empty `corrections` string when the script passes cleanly.

## `base_script` persistence

`writer_critic_graph` is the only node that writes `Run.base_script`. It does so after a successful loop exit. If the loop exits with `is_fatal_error`, the script is not persisted and a fatal error propagates upstream.

## Testing

Inner nodes are tested against `WriterCriticState` directly (not `PersonaRunState`). See `src/tests/test_writer_node.py` and `src/tests/test_critic_node.py`.
