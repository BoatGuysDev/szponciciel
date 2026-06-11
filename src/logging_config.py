import logging

import structlog

from config import settings

_configured = False


def setup_logging() -> None:
    """Configures structlog once: JSON in production, human-readable otherwise.

    Idempotent — safe to call from every entrypoint (CLI, langgraph dev).
    Bound context vars (run_id, persona_id) are merged into every event, so
    nodes only need ``get_logger(__name__)`` and the orchestrator binds context.
    """

    global _configured
    if _configured:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    renderer = (
        structlog.processors.JSONRenderer() if settings.run_mode == "production" else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=level)
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str):
    return structlog.get_logger(name)
