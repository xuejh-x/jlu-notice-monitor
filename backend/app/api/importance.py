from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ImportanceRule
from app.services.importance import ensure_importance_rules, rescore_all_notices, restore_default_rules

router = APIRouter(prefix="/importance", tags=["importance"])


class RuleInput(BaseModel):
    keyword: str = Field(min_length=1, max_length=200)
    weight: int = Field(ge=-50, le=50)
    enabled: bool = True

    @field_validator("keyword")
    @classmethod
    def clean_keyword(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("keyword cannot be blank")
        return cleaned


class RuleUpdate(BaseModel):
    keyword: str | None = Field(default=None, min_length=1, max_length=200)
    weight: int | None = Field(default=None, ge=-50, le=50)
    enabled: bool | None = None

    @field_validator("keyword")
    @classmethod
    def clean_keyword(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("keyword cannot be blank")
        return cleaned


class RuleOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    keyword: str
    weight: int
    enabled: bool
    is_system_default: bool


def _ensure_unique(db: Session, keyword: str, exclude_id: int | None = None) -> None:
    query = select(ImportanceRule.id).where(func.lower(ImportanceRule.keyword) == keyword.casefold())
    if exclude_id is not None:
        query = query.where(ImportanceRule.id != exclude_id)
    if db.scalar(query) is not None:
        raise HTTPException(status_code=409, detail="Keyword rule already exists")


@router.get("/rules", response_model=list[RuleOutput])
def list_rules(db: Session = Depends(get_db)) -> list[ImportanceRule]:
    ensure_importance_rules(db)
    return list(db.scalars(select(ImportanceRule).order_by(ImportanceRule.position, ImportanceRule.id)).all())


@router.post("/rules", response_model=RuleOutput, status_code=status.HTTP_201_CREATED)
def create_rule(payload: RuleInput, db: Session = Depends(get_db)) -> ImportanceRule:
    ensure_importance_rules(db)
    _ensure_unique(db, payload.keyword)
    position = (db.scalar(select(func.max(ImportanceRule.position))) or 0) + 1
    rule = ImportanceRule(**payload.model_dump(), is_system_default=False, position=position)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    rescore_all_notices(db)
    return rule


@router.patch("/rules/{rule_id}", response_model=RuleOutput)
def update_rule(rule_id: int, payload: RuleUpdate, db: Session = Depends(get_db)) -> ImportanceRule:
    rule = db.get(ImportanceRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Importance rule not found")
    values = payload.model_dump(exclude_unset=True)
    if "keyword" in values:
        _ensure_unique(db, values["keyword"], rule_id)
    for key, value in values.items():
        setattr(rule, key, value)
    rule.is_system_default = False
    db.commit()
    db.refresh(rule)
    rescore_all_notices(db)
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)) -> dict[str, int]:
    rule = db.get(ImportanceRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Importance rule not found")
    db.delete(rule)
    db.commit()
    return {"rescored": rescore_all_notices(db)}


@router.post("/restore-defaults")
def restore_defaults(db: Session = Depends(get_db)) -> dict[str, int]:
    return {"rescored": restore_default_rules(db)}


@router.post("/rescore")
def rescore(db: Session = Depends(get_db)) -> dict[str, int]:
    return {"rescored": rescore_all_notices(db)}
