from __future__ import annotations

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.cloud.api import get_cloud_db, router


app = FastAPI(title="JLU Notice Monitor Cloud API", version=__version__)
app.include_router(router)


@app.get("/health", include_in_schema=False)
def health(db: Session = Depends(get_cloud_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok", "service": "jlu-notice-cloud"}
