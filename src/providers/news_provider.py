from typing import Any, Dict, List, Protocol

try:
    from langchain_community.tools.tavily_search import TavilySearchResults
except Exception:  # pragma: no cover - optional dependency in tests
    TavilySearchResults = None


class NewsProvider(Protocol):
    def fetch(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]: ...


class TavilyNewsProvider:
    """Wrapper around TavilySearchResults (when available).

    Returns a list of dicts with keys: url, headline, summary, raw_text, fetch_score,
    timestamp, source, language
    """

    def __init__(self, max_results: int = 10):
        if TavilySearchResults is None:
            raise RuntimeError("TavilySearchResults not available in this environment")
        self.tool = TavilySearchResults(max_results=max_results)

    def fetch(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        raw = self.tool.invoke({"query": query})
        results: List[Dict[str, Any]] = []
        for r in raw:
            results.append(
                {
                    "url": r.get("url"),
                    "headline": r.get("title"),
                    "summary": r.get("summary") or r.get("snippet") or "",
                    "raw_text": r.get("raw_text"),
                    "fetch_score": float(r.get("score", 0.0)),
                    "timestamp": r.get("published_at"),
                    "source": r.get("domain"),
                    "language": r.get("language", "en"),
                }
            )

        return results


__all__ = ["NewsProvider", "TavilyNewsProvider"]
