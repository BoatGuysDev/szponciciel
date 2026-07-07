from __future__ import annotations

import re
from datetime import date, datetime, time, timezone
from typing import Any, TypedDict

from services.research_analytics_service import ResearchAnalyticsSummary


class ResearchScore(TypedDict):
    final_research_score: float
    category_performance_score: float
    similar_topic_performance_score: float
    content_fit_score: float
    recency_score: float
    exploration_bonus: float


def compute_research_score(
    *,
    topic: str,
    category: str,
    analytics: ResearchAnalyticsSummary,
    hook_strength: float,
    urgency: float,
    emotional_intensity: float,
    audience_breadth: float,
    search_kind: str,
    published_at: Any | None = None,
    published_date: Any | None = None,
) -> ResearchScore:
    category_score = _category_score(category, analytics)
    topic_score = _topic_score(topic, analytics)
    content_fit_score = _content_fit_score(
        hook_strength=hook_strength,
        urgency=urgency,
        emotional_intensity=emotional_intensity,
        audience_breadth=audience_breadth,
    )
    recency_score = _recency_score(published_at or published_date)
    exploration_bonus = 1.0 if search_kind == "explore" or category in analytics["underexplored_categories"] else 0.0

    final_score = (
        0.45 * category_score
        + 0.25 * topic_score
        + 0.15 * content_fit_score
        + 0.10 * recency_score
        + 0.05 * exploration_bonus
    )
    return {
        "final_research_score": round(min(final_score, 1.0), 4),
        "category_performance_score": round(category_score, 4),
        "similar_topic_performance_score": round(topic_score, 4),
        "content_fit_score": round(content_fit_score, 4),
        "recency_score": recency_score,
        "exploration_bonus": exploration_bonus,
    }


def _category_score(category: str, analytics: ResearchAnalyticsSummary) -> float:
    for item in analytics["top_categories"]:
        if item["name"] == category:
            return item["score"]
    return 0.5


def _topic_score(topic: str, analytics: ResearchAnalyticsSummary) -> float:
    topic_tokens = _tokens(topic)
    if not topic_tokens:
        return 0.5

    best_score = 0.5
    for item in analytics["top_topics"]:
        overlap = _jaccard(topic_tokens, _tokens(item["name"]))
        if overlap > 0:
            best_score = max(best_score, item["score"] * overlap)
    return best_score


def _content_fit_score(
    *,
    hook_strength: float,
    urgency: float,
    emotional_intensity: float,
    audience_breadth: float,
) -> float:
    values = [
        _clamp(hook_strength),
        _clamp(urgency),
        _clamp(emotional_intensity),
        _clamp(audience_breadth),
    ]
    return sum(values) / len(values)


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _clamp(value: Any) -> float:
    return max(0.0, min(float(value), 1.0))


def _recency_score(published_value: Any) -> float:
    published_at = _parse_published_datetime(published_value)
    if published_at is None:
        return 0.5

    age_hours = max((datetime.now(timezone.utc) - published_at).total_seconds() / 3600, 0.0)
    return round(max(0.0, 1.0 - age_hours / 72.0), 4)


def _parse_published_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time(hour=12), tzinfo=timezone.utc)
    elif isinstance(value, (int, float)):
        parsed = datetime.fromtimestamp(value, tz=timezone.utc)
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
