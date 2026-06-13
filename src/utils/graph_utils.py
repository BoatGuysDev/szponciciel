from collections.abc import Sequence
from typing import Any

from langgraph.errors import NodeError
from structlog.stdlib import BoundLogger

from utils.logging import describe_exception, log_exception


def build_error_handler(
    log: BoundLogger,
    event: str,
    message: str,
    *,
    context_keys: Sequence[str] = (),
):
    """Build a node error handler that logs and returns a fatal state update."""

    def error_handler(state: dict[str, Any], error: NodeError) -> dict[str, Any]:
        context = {key: state.get(key) for key in context_keys if state.get(key) is not None}
        log_exception(log, event, error.error, node=error.node, **context)
        return {
            "is_fatal_error": True,
            "error_message": f"{message}: {describe_exception(error.error)}",
        }

    return error_handler
