from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.classifier import score_importance
from app.config import load_yaml
from app.models import ImportanceRule, Notice


def system_default_rules() -> list[tuple[str, int]]:
    scoring = load_yaml("keywords.yaml").get("scoring", {})
    defaults: list[tuple[str, int]] = []
    seen: set[str] = set()
    for group in ("strong", "recommended", "interests", "low"):
        config = scoring.get(group, {})
        weight = int(config.get("weight", 0))
        for raw_keyword in config.get("keywords", []):
            keyword = str(raw_keyword).strip()
            folded = keyword.casefold()
            if keyword and folded not in seen:
                defaults.append((keyword, weight))
                seen.add(folded)
    return defaults


def ensure_importance_rules(db: Session) -> None:
    if db.scalar(select(ImportanceRule.id).limit(1)) is not None:
        return
    for position, (keyword, weight) in enumerate(system_default_rules()):
        db.add(
            ImportanceRule(
                keyword=keyword,
                weight=weight,
                enabled=True,
                is_system_default=True,
                position=position,
            )
        )
    db.commit()


def enabled_rule_values(db: Session) -> list[tuple[str, int]]:
    ensure_importance_rules(db)
    rules = db.scalars(
        select(ImportanceRule)
        .where(ImportanceRule.enabled.is_(True))
        .order_by(ImportanceRule.position, ImportanceRule.id)
    ).all()
    return [(rule.keyword, rule.weight) for rule in rules]


def rescore_all_notices(db: Session) -> int:
    values = enabled_rule_values(db)
    notices = db.scalars(select(Notice).order_by(Notice.id)).all()
    for notice in notices:
        notice.importance_score = score_importance(
            notice.title,
            notice.content,
            notice.category,
            notice.registration_deadline,
            keyword_rules=values,
        )
    db.commit()
    return len(notices)


def restore_default_rules(db: Session) -> int:
    db.execute(delete(ImportanceRule))
    db.commit()
    ensure_importance_rules(db)
    return rescore_all_notices(db)
