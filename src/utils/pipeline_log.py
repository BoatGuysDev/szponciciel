from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel
from structlog.contextvars import get_contextvars

from config import settings
from utils.logging import describe_exception

_log = structlog.get_logger(__name__)
_runs: dict[str, dict[str, Any]] = {}
_current_run_id: ContextVar[str | None] = ContextVar("pipeline_log_run_id", default=None)
_current_node: ContextVar[dict[str, Any] | None] = ContextVar("pipeline_log_node", default=None)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _safe(value.model_dump())
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, BaseException):
        return {
            "type": value.__class__.__name__,
            "message": str(value),
        }
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return repr(value)


def _duration_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)


def _summary(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return {"type": value.__class__.__name__}
    if isinstance(value, dict):
        return {"type": "dict", "keys": sorted(str(key) for key in value.keys())}
    if isinstance(value, list):
        return {"type": "list", "count": len(value)}
    if isinstance(value, tuple):
        return {"type": "tuple", "count": len(value)}
    if isinstance(value, str):
        return {"type": "str", "chars": len(value)}
    if value is None:
        return {"type": "none"}
    return {"type": value.__class__.__name__}


def _run_for(run_id: str) -> dict[str, Any] | None:
    return _runs.get(run_id)


def _current_run() -> dict[str, Any] | None:
    run_id = _current_run_id.get() or get_contextvars().get("run_id")
    if not run_id:
        return None
    return _run_for(str(run_id))


def _append_to_current_node(key: str, item: dict[str, Any]) -> None:
    node = _current_node.get()
    if node is not None:
        node.setdefault(key, []).append(item)
        return

    run = _current_run()
    if run is not None:
        run.setdefault(key, []).append(item)


def _current_node_name() -> str | None:
    node = _current_node.get()
    if node is None:
        return None
    return node.get("name")


def start_run(run_id: str, *, prompt: str | None = None) -> None:
    _runs[run_id] = {
        "event": "pipeline.run",
        "run_id": run_id,
        "started_at": _now(),
        "input": {"prompt": prompt},
        "nodes": [],
        "events": [],
        "agent_calls": [],
        "tool_calls": [],
        "errors": [],
    }


def update_run(run_id: str, **fields: Any) -> None:
    run = _run_for(run_id)
    if run is not None:
        run.update(_safe(fields))


@contextmanager
def node_span(run_id: str, name: str, *, parameters: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    run = _run_for(run_id)
    if run is None:
        yield {}
        return

    start = time.perf_counter()
    node = {
        "name": name,
        "entered_at": _now(),
        "parameters": _safe(parameters or {}),
        "events": [],
        "agent_calls": [],
        "tool_calls": [],
    }
    run["nodes"].append(node)
    run_token = _current_run_id.set(run_id)
    node_token = _current_node.set(node)
    _log.info("node.start", run_id=run_id, node=name)
    try:
        yield node
    except BaseException as exc:
        node["exited_at"] = _now()
        node["duration_ms"] = _duration_ms(start)
        node["error"] = _safe(exc)
        record_error(exc, node=name)
        _log.error(
            "node.failed",
            run_id=run_id,
            node=name,
            duration_ms=node["duration_ms"],
            error_type=exc.__class__.__name__,
            error_message=str(exc),
        )
        raise
    else:
        node["exited_at"] = _now()
        node["duration_ms"] = _duration_ms(start)
        _log.info("node.completed", run_id=run_id, node=name, duration_ms=node["duration_ms"])
    finally:
        _current_node.reset(node_token)
        _current_run_id.reset(run_token)


def instrument_node(name: str, node: Any) -> Callable[[dict[str, Any]], Any]:
    def wrapped(state: dict[str, Any]) -> Any:
        run_id = state.get("run_id")
        if not run_id:
            if callable(node):
                return node(state)
            return node.invoke(state)

        with node_span(str(run_id), name, parameters={"state": state}) as span:
            if callable(node):
                result = node(state)
            else:
                result = node.invoke(state)
            span["output"] = _safe(result)
            return result

    wrapped.__name__ = name
    return wrapped


@contextmanager
def agent_span(
    name: str,
    *,
    model: str,
    prompt: str,
    response_format: str,
    system_prompt: str | None = None,
    tools: list[str] | None = None,
) -> Iterator[dict[str, Any]]:
    start = time.perf_counter()
    call = {
        "name": name,
        "started_at": _now(),
        "model": model,
        "response_format": response_format,
        "tools": tools or [],
        "input": {
            "system_prompt": system_prompt,
            "prompt": prompt,
        },
    }
    _append_to_current_node("agent_calls", call)
    _log.info(
        "agent.start",
        node=_current_node_name(),
        agent=name,
        model=model,
        response_format=response_format,
        prompt_chars=len(prompt),
        tools=tools or [],
    )
    try:
        yield call
    except BaseException as exc:
        call["completed_at"] = _now()
        call["duration_ms"] = _duration_ms(start)
        call["error"] = _safe(exc)
        _log.error(
            "agent.failed",
            node=_current_node_name(),
            agent=name,
            model=model,
            duration_ms=call["duration_ms"],
            error_type=exc.__class__.__name__,
            error_message=str(exc),
        )
        raise
    else:
        call["completed_at"] = _now()
        call["duration_ms"] = _duration_ms(start)
        _log.info(
            "agent.completed",
            node=_current_node_name(),
            agent=name,
            model=model,
            duration_ms=call["duration_ms"],
            output=_summary(call.get("output")),
        )
    finally:
        call.setdefault("completed_at", _now())
        call.setdefault("duration_ms", _duration_ms(start))


@contextmanager
def tool_span(name: str, *, input: dict[str, Any]) -> Iterator[dict[str, Any]]:
    start = time.perf_counter()
    call = {
        "name": name,
        "started_at": _now(),
        "input": _safe(input),
    }
    _append_to_current_node("tool_calls", call)
    _log.info("tool.start", node=_current_node_name(), tool=name, input=_safe(input))
    try:
        yield call
    except BaseException as exc:
        call["completed_at"] = _now()
        call["duration_ms"] = _duration_ms(start)
        call["error"] = _safe(exc)
        _log.error(
            "tool.failed",
            node=_current_node_name(),
            tool=name,
            duration_ms=call["duration_ms"],
            error_type=exc.__class__.__name__,
            error_message=str(exc),
        )
        raise
    else:
        call["completed_at"] = _now()
        call["duration_ms"] = _duration_ms(start)
        _log.info(
            "tool.completed",
            node=_current_node_name(),
            tool=name,
            duration_ms=call["duration_ms"],
            output=_summary(call.get("output")),
        )
    finally:
        call.setdefault("completed_at", _now())
        call.setdefault("duration_ms", _duration_ms(start))


def record_log_event(event: dict[str, Any]) -> None:
    run = _current_run()
    if run is None:
        return

    item = _safe({k: v for k, v in event.items() if k not in {"_record", "exc_info", "stack_info"}})
    node = _current_node.get()
    if node is not None:
        node.setdefault("events", []).append(item)
    else:
        run.setdefault("events", []).append(item)


def record_error(exc: BaseException, **context: Any) -> None:
    run = _current_run()
    if run is None:
        return

    run.setdefault("errors", []).append(
        {
            "timestamp": _now(),
            "type": exc.__class__.__name__,
            "message": str(exc),
            "description": describe_exception(exc),
            "context": _safe(context),
        }
    )


def finish_run(
    run_id: str, *, status: str, error_message: str | None = None, outcomes: list[dict] | None = None
) -> None:
    run = _runs.pop(run_id, None)
    if run is None:
        return

    run["completed_at"] = _now()
    run["status"] = status
    run["error_message"] = error_message
    run["outcomes"] = _safe(outcomes or [])

    settings.log_file.parent.mkdir(parents=True, exist_ok=True)
    with settings.log_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(_safe(run), ensure_ascii=False) + "\n")
