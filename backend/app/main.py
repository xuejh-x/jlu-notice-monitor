from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import api_router
from app.api.routes import health_status
from app.config import get_settings, load_yaml
from app.crawler import crawler_manager, scheduler_manager, startup_sync
from app.database import SessionLocal, close_db, get_db, init_db
from app.logging_config import configure_logging, log_event
from app.paths import ensure_runtime_directories
from app.runtime import mark_started, mark_stopped
from app.services.importance import ensure_importance_rules
from fastapi import Depends
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    ensure_runtime_directories(settings.environment, settings.app_data_dir)
    log_file = configure_logging()
    log_event(logger, logging.INFO, "application_starting", environment=settings.environment)
    init_db()
    with SessionLocal() as db:
        crawler_manager._sync_sources(db, load_yaml("sources.yaml").get("sources", []))
        ensure_importance_rules(db)
    mark_started()
    if settings.effective_startup_sync_enabled:
        startup_sync.trigger_once()
    scheduler_manager.start()
    log_event(logger, logging.INFO, "application_started", log_file=str(log_file))
    try:
        yield
    finally:
        log_event(logger, logging.INFO, "application_stopping")
        await scheduler_manager.shutdown()
        await crawler_manager.shutdown()
        close_db()
        mark_stopped()
        log_event(logger, logging.INFO, "application_stopped")


settings = get_settings()
app = FastAPI(title="JLU Notice Monitor API", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Notice-Hub-Admin-Key"],
)
app.include_router(api_router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for raw in exc.errors():
        item = dict(raw)
        if any(
            str(part).lower() in {"password", "token", "cookie", "admin_key", "authorization"}
            for part in item.get("loc", ())
        ):
            item.pop("input", None)
        errors.append(item)
    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/health", include_in_schema=False)
def health(db: Session = Depends(get_db)):
    return health_status(db)
