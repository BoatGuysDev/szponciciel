from langchain_core.tools import tool
from langchain_tavily import TavilyExtract

from utils.pipeline_log import tool_span


@tool
def fetch_article_content(url: str) -> dict:
    """Fetches the raw text content of a news article from its URL."""

    extract = TavilyExtract()
    with tool_span("tavily.extract", input={"url": url}) as call:
        response = extract.invoke({"urls": [url]})
        call["output"] = response
        return response
