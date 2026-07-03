from __future__ import annotations

NEWS_CATEGORIES: list[tuple[str, str]] = [
    ("ai", "latest artificial intelligence breakthroughs"),
    ("tech", "latest technology and startup news"),
    ("finance", "latest stock market and finance news"),
    ("politics", "latest politics and government news"),
    ("world", "latest world and international news"),
]

NEWS_CATEGORY_IDS = {category for category, _ in NEWS_CATEGORIES}
