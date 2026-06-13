from typing import Any

from structlog.stdlib import BoundLogger


def describe_exception(exc: BaseException) -> str:
    """Format an exception with its type so the message stays explicit."""

    message = str(exc)
    if message:
        return f"{exc.__class__.__name__}: {message}"
    return exc.__class__.__name__


def log_exception(log: BoundLogger, event: str, exc: BaseException, **context: Any) -> None:
    """Log an exception with traceback and structured context."""

    log.exception(event, **context, error_type=exc.__class__.__name__, error_message=str(exc))
