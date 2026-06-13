import logging
import sys
from datetime import datetime

import structlog
from structlog.stdlib import BoundLogger, LoggerFactory, ProcessorFormatter

from config import settings
from utils.pipeline_log import record_log_event

_configured = False

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_LEVEL_COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[1;31m",
}


def _color(text: str, code: str, *, enabled: bool) -> str:
    if not enabled or not code:
        return text
    return f"{code}{text}{_RESET}"


def _use_console_colors() -> bool:
    return settings.run_mode != "production" and sys.stdout.isatty()


def _format_console_timestamp(timestamp: str) -> str:
    if not timestamp:
        return ""

    normalized = timestamp.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return timestamp

    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return parsed.strftime("%Y-%m-%d %H:%M:%S:%f")


def _console_renderer(_: object, __: str, event_dict: dict) -> str:
    timestamp = _format_console_timestamp(event_dict.pop("timestamp", ""))
    level = event_dict.pop("level", "").upper()
    message = event_dict.pop("event", "")
    exception = event_dict.pop("exception", None)
    use_colors = _use_console_colors()

    params = " ".join(f"{key}={value!r}" for key, value in sorted(event_dict.items()))
    rendered = " ".join(
        (
            _color(timestamp, _BOLD, enabled=use_colors),
            _color(f"{level:<7}", _LEVEL_COLORS.get(level, ""), enabled=use_colors),
            _color(str(message), _BOLD, enabled=use_colors),
        )
    )
    if params:
        rendered = f"{rendered} {_color(params, _BOLD, enabled=use_colors)}"
    if exception:
        rendered = f"{rendered}\n{exception}"
    return rendered


def _record_app_event(_: object, __: str, event_dict: dict) -> dict:
    record_log_event(event_dict)
    return event_dict


def setup_logging() -> None:
    """Configures live console logs once.

    Idempotent - safe to call from every entrypoint (CLI, langgraph dev).
    Bound context vars (run_id, persona_id) are merged into every event, so
    nodes only need ``get_logger(__name__)`` and the orchestrator binds context.
    Structured run logs are accumulated by ``utils.pipeline_log`` and flushed
    once per run in ``finalize_node``.
    """

    global _configured
    if _configured:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _record_app_event,
    ]

    structlog.configure(
        processors=shared_processors + [ProcessorFormatter.wrap_for_formatter],
        wrapper_class=BoundLogger,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(
        ProcessorFormatter(
            processors=[
                ProcessorFormatter.remove_processors_meta,
                structlog.processors.format_exc_info,
                _console_renderer,
            ],
            foreign_pre_chain=shared_processors,
        )
    )
    root.addHandler(console_handler)

    for noisy in (
        "httpx",
        "httpcore",
        "urllib3",
        "langchain",
        "langchain_core",
        "langchain_google_genai",
        "langgraph",
        "google",
        "google_genai",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> BoundLogger:
    return structlog.get_logger(name)
