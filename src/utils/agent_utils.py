from collections.abc import Sequence
from typing import Any, TypeVar, cast

from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.types import RetryPolicy
from pydantic import BaseModel

from config import settings
from utils.pipeline_log import agent_span

T = TypeVar("T", bound=BaseModel)


class AgentResponseError(ValueError):
    """Raised when an agent response is missing the expected structured output."""


LLM_RETRY = RetryPolicy(max_attempts=3, backoff_factor=2.0, retry_on=(AgentResponseError, ValueError))


def call_agent(
    system_prompt: str,
    response_format: type[T],
    *,
    prompt: str,
    model: str | None = None,
    tools: Sequence[Any] | None = None,
    _agent: Any | None = None,
) -> T:
    """Create an agent, invoke it, and return its structured response."""

    agent = _agent
    if agent is None:
        resolved_model = model or settings.llm_model
        kwargs: dict[str, Any] = {
            "model": ChatGoogleGenerativeAI(model=resolved_model),
            "system_prompt": system_prompt,
            "response_format": response_format,
        }
        if tools is not None:
            kwargs["tools"] = list(tools)
        agent = create_agent(**kwargs)
    else:
        resolved_model = model or settings.llm_model

    tool_names = [getattr(tool, "name", getattr(tool, "__name__", repr(tool))) for tool in tools or []]
    with agent_span(
        response_format.__name__,
        model=resolved_model,
        prompt=prompt,
        response_format=response_format.__name__,
        system_prompt=system_prompt,
        tools=tool_names,
    ) as call:
        response = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        call["raw_output"] = response

        if not isinstance(response, dict):
            raise AgentResponseError("Agent response was not a mapping.")

        structured_response = response.get("structured_response")
        if structured_response is None:
            raise AgentResponseError("Agent response did not include structured_response.")

        call["output"] = structured_response
        return cast(T, structured_response)
