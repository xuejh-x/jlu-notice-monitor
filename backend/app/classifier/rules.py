from __future__ import annotations

from datetime import date

from app.config import load_yaml


def _contains(text: str, keyword: str) -> bool:
    return keyword.casefold() in text.casefold()


def classify_notice(title: str, content: str) -> str:
    text = f"{title}\n{content}"
    categories = load_yaml("keywords.yaml").get("categories", {})
    best_category = "other"
    best_hits = 0
    for category, keywords in categories.items():
        hits = sum(1 for keyword in keywords if _contains(text, str(keyword)))
        if hits > best_hits:
            best_category, best_hits = category, hits
    return best_category


def score_importance(
    title: str,
    content: str,
    category: str,
    deadline: date | None = None,
    today: date | None = None,
) -> int:
    text = f"{title}\n{content}"
    config = load_yaml("keywords.yaml").get("scoring", {})
    score = 20
    category_boost = {
        "algorithm_competition": 35,
        "cybersecurity_competition": 38,
        "innovation_competition": 22,
        "research": 18,
        "training": 18,
        "internship": 16,
        "postgraduate_recommendation": 20,
        "scholarship": 12,
        "academic": 4,
        "other": 0,
    }
    score += category_boost.get(category, 0)
    for group in ("strong", "recommended", "interests", "low"):
        group_config = config.get(group, {})
        hits = sum(1 for keyword in group_config.get("keywords", []) if _contains(text, str(keyword)))
        if hits:
            score += int(group_config.get("weight", 0)) + min(hits - 1, 3) * 3
    if deadline:
        days = (deadline - (today or date.today())).days
        if 0 <= days <= 3:
            score += 20
        elif days < 0:
            score -= 15
    return max(0, min(100, score))

