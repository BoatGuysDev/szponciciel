from types import SimpleNamespace

import logging_config
from config import settings


def test_console_renderer_plain_when_not_tty(monkeypatch):
    monkeypatch.setattr(settings, "run_mode", "development")
    monkeypatch.setattr(logging_config.sys, "stdout", SimpleNamespace(isatty=lambda: False))

    rendered = logging_config._console_renderer(
        None,
        "info",
        {
            "timestamp": "2026-06-13T17:00:00Z",
            "level": "info",
            "event": "node.start",
            "node": "writer_node",
        },
    )

    assert rendered == "2026-06-13T17:00:00Z INFO    node.start node='writer_node'"
    assert "\033[" not in rendered


def test_console_renderer_uses_colors_for_local_tty(monkeypatch):
    monkeypatch.setattr(settings, "run_mode", "development")
    monkeypatch.setattr(logging_config.sys, "stdout", SimpleNamespace(isatty=lambda: True))

    rendered = logging_config._console_renderer(
        None,
        "error",
        {
            "timestamp": "2026-06-13T17:00:00Z",
            "level": "error",
            "event": "writer.failed",
            "error_type": "AgentResponseError",
        },
    )

    assert "\033[2m2026-06-13T17:00:00Z\033[0m" in rendered
    assert "\033[31mERROR  \033[0m" in rendered
    assert "\033[1mwriter.failed\033[0m" in rendered
    assert "\033[2merror_type='AgentResponseError'\033[0m" in rendered
