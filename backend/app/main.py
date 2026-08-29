from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import api_router
from app.api.routes import health_status
from app.config import get_settings, load_yaml
from app.crawler import crawler_manager
from app.database import SessionLocal, close_db, get_db, init_db
from app.logging_config import configure_logging
from app.paths import ensure_runtime_directories
from fastapi import Depends
from sqlalchemy.orm import Session


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    ensure_runtime_directories(settings.environment, settings.app_data_dir)
    configure_logging()
    init_db()
    with SessionLocal() as db:
        crawler_manager._sync_sources(db, load_yaml("sources.yaml").get("sources", []))
    try:
        yield
    finally:
        await crawler_manager.shutdown()
        close_db()


settings = get_settings()
app = FastAPI(title="JLU Notice Monitor API", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(api_router)


@app.get("/health", include_in_schema=False)
def health(db: Session = Depends(get_db)):
    return health_status(db)
