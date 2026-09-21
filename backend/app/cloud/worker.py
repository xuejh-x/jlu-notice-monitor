from __future__ import annotations

import asyncio
import signal

from app.config import load_yaml
from app.crawler import crawler_manager, scheduler_manager
from app.database import SessionLocal
from app.services.importance import ensure_importance_rules


async def run_worker() -> None:
    with SessionLocal() as db:
        crawler_manager._sync_sources(db, load_yaml("sources.yaml").get("sources", []))
        ensure_importance_rules(db)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(name, stop.set)
        except (NotImplementedError, RuntimeError):
            pass
    scheduler_manager.start()
    try:
        await stop.wait()
    finally:
        await scheduler_manager.shutdown()
        await crawler_manager.shutdown()


if __name__ == "__main__":
    asyncio.run(run_worker())
