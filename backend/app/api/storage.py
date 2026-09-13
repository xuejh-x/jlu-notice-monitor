from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services.retention import cleanup_notices, storage_status


router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("/status")
def get_storage_status(db: Session = Depends(get_db)) -> dict[str, object]:
    return storage_status(db)


@router.post("/cleanup")
def clean_old_notifications(db: Session = Depends(get_db)) -> dict[str, object]:
    result = cleanup_notices(db, get_settings())
    db.commit()
    return {"deleted_count": result.deleted_count, **storage_status(db)}
