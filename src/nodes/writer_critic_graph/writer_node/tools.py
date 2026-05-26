from langchain_core.tools import tool
from langchain_tavily import TavilyExtract


@tool
def fetch_article_content(url: str) -> dict:
    """Fetches the raw text content of a news article from its URL."""

    extract = TavilyExtract()
    response = extract.invoke({"urls": [url]})
    return response
