import json
from unittest.mock import patch

from config import settings
from utils.pipeline_log import agent_span, finish_run, node_span, start_run, tool_span


def test_pipeline_log_writes_one_wide_event(tmp_path, monkeypatch):
    log_file = tmp_path / "pipeline.jsonl"
    monkeypatch.setattr(settings, "log_file", log_file)

    start_run("run-1", prompt="make a video")
    with node_span("run-1", "researcher_node", parameters={"topic": "AI"}) as node:
        with tool_span("tavily.search", input={"query": "AI"}) as tool:
            tool["output"] = [{"title": "News"}]
        with agent_span(
            "researcher.score_articles",
            model="gemini-test",
            prompt="score these",
            response_format="ArticleRanking",
        ) as agent:
            agent["output"] = {"rankings": [{"index": 0, "virality_score": 0.9}]}
        node["output"] = {"source_article_title": "News"}

    finish_run("run-1", status="completed", outcomes=[{"status": "completed"}])

    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    payload = json.loads(lines[0])
    assert payload["event"] == "pipeline.run"
    assert payload["run_id"] == "run-1"
    assert payload["status"] == "completed"
    assert payload["input"] == {"prompt": "make a video"}
    assert payload["outcomes"] == [{"status": "completed"}]

    [node] = payload["nodes"]
    assert node["name"] == "researcher_node"
    assert node["parameters"] == {"topic": "AI"}
    assert node["output"] == {"source_article_title": "News"}
    assert node["tool_calls"][0]["name"] == "tavily.search"
    assert node["agent_calls"][0]["name"] == "researcher.score_articles"


def test_pipeline_spans_emit_live_progress_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "log_file", tmp_path / "pipeline.jsonl")

    start_run("run-2", prompt="make another video")
    with patch("utils.pipeline_log._log") as log:
        with node_span("run-2", "writer_node"):
            with tool_span("tavily.search", input={"query": "AI"}) as tool:
                tool["output"] = [{"title": "News"}]
            with agent_span(
                "WriterAgentResponseFormat",
                model="gemini-test",
                prompt="write this",
                response_format="WriterAgentResponseFormat",
            ) as agent:
                agent["output"] = {"draft_script": "Script"}

    events = [call.args[0] for call in log.info.call_args_list]
    assert events == [
        "node.start",
        "tool.start",
        "tool.completed",
        "agent.start",
        "agent.completed",
        "node.completed",
    ]
