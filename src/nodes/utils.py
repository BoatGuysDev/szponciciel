from typing import Any

from langchain.messages import HumanMessage


class AgentResponseError(RuntimeError):
    """Raised when an agent cannot be invoked or its response is unusable."""


def invoke_agent_response(agent: Any, prompt: str) -> dict[str, Any]:
    """Invoke a LangChain agent and return the raw response payload."""

    try:
        response = agent.invoke({"messages": [HumanMessage(content=prompt)]})
    except Exception as e:
        raise AgentResponseError(f"Agent invocation failed: {e}") from e

    if not isinstance(response, dict):
        raise AgentResponseError("Agent response was not a mapping.")

    return response


def invoke_agent(agent: Any, prompt: str) -> str:
    """Invoke a LangChain agent and return the last message content.

    Raises:
        AgentResponseError: if the invocation fails or the response is malformed.
    """

    response = invoke_agent_response(agent, prompt)

    try:
        return response["messages"][-1].content
    except (AttributeError, KeyError, IndexError, TypeError) as e:
        raise AgentResponseError("Agent response did not include a final message content.") from e
