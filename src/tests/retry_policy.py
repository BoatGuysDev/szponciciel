from langgraph.types import RetryPolicy

from utils.agent_utils import AgentResponseError

FAST_LLM_RETRY = RetryPolicy(
    initial_interval=0.0,
    backoff_factor=1.0,
    max_interval=0.0,
    max_attempts=3,
    jitter=False,
    retry_on=(AgentResponseError, ValueError),
)
