import logging
import sys

import structlog
from structlog.stdlib import BoundLogger, LoggerFactory, ProcessorFormatter

from config import settings

_configured = False


def setup_logging() -> None:
    """Configures live console logs and a JSON log file once.

    Idempotent - safe to call from every entrypoint (CLI, langgraph dev).
    Bound context vars (run_id, persona_id) are merged into every event, so
    nodes only need ``get_logger(__name__)`` and the orchestrator binds context.
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
        structlog.processors.format_exc_info,
    ]
    console_renderer = (
        structlog.processors.JSONRenderer() if settings.run_mode == "production" else structlog.dev.ConsoleRenderer()
    )
    settings.log_file.parent.mkdir(parents=True, exist_ok=True)

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
            processors=[ProcessorFormatter.remove_processors_meta, console_renderer],
            foreign_pre_chain=shared_processors,
        )
    )
    root.addHandler(console_handler)

    file_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(
        ProcessorFormatter(
            processors=[ProcessorFormatter.remove_processors_meta, structlog.processors.JSONRenderer()],
            foreign_pre_chain=shared_processors,
        )
    )
    root.addHandler(file_handler)

    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> BoundLogger:
    return structlog.get_logger(name)
