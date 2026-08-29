from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

import uvicorn

from app.config import get_settings, load_yaml
from app.crawler import crawler_manager
from app.database import init_db
from app.logging_config import configure_logging
from app.sources import build_source
from app.sources.oa import OASource


def _json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


async def _crawl(source: str | None, bootstrap: bool = False) -> None:
    result = await crawler_manager.run(source_code=source, bootstrap=bootstrap)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=_json_default))


async def _test_source(code: str) -> None:
    configs = load_yaml("sources.yaml").get("sources", [])
    config = next((item for item in configs if item.get("code") == code), None)
    if config is None:
        raise SystemExit(f"Unknown source: {code}")
    adapter = build_source(config)
    try:
        items = await adapter.fetch_list()
        print(f"{code}: list items={len(items)}")
        if items:
            detail = await adapter.fetch_detail(items[0])
            summary = {
                "title": detail.title,
                "url": detail.url,
                "publish_date": detail.publish_date,
                "publisher": detail.publisher,
                "content_length": len(detail.content),
                "content_preview": detail.content[:300],
                "attachments": [item.model_dump() for item in detail.attachments],
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default))
    finally:
        await adapter.close()


async def _oa_login() -> None:
    config = next(
        item for item in load_yaml("sources.yaml").get("sources", []) if item.get("code") == "oa"
    )
    source = OASource(config)
    try:
        await source.login_setup()
    finally:
        await source.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app")
    subparsers = parser.add_subparsers(dest="command", required=True)
    serve = subparsers.add_parser("serve", help="start FastAPI server")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    run = subparsers.add_parser("run", help="crawl once, then start FastAPI")
    run.add_argument("--host")
    run.add_argument("--port", type=int)
    subparsers.add_parser("bootstrap", help="create initial baseline without NEW events")
    crawl = subparsers.add_parser("crawl", help="crawl enabled sources")
    crawl.add_argument("--source")
    test = subparsers.add_parser("test-source", help="fetch and parse one source without writing DB")
    test.add_argument("source")
    subparsers.add_parser("oa-login", help="open Edge for a user-driven OA login")
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = build_parser().parse_args()
    configure_logging()
    init_db()
    settings = get_settings()
    host = getattr(args, "host", None) or settings.host
    port = getattr(args, "port", None) or settings.port
    if args.command == "serve":
        uvicorn.run("app.main:app", host=host, port=port, reload=False, log_config=None)
    elif args.command == "run":
        asyncio.run(_crawl(None))
        uvicorn.run("app.main:app", host=host, port=port, reload=False, log_config=None)
    elif args.command == "bootstrap":
        asyncio.run(_crawl(None, bootstrap=True))
    elif args.command == "crawl":
        asyncio.run(_crawl(args.source))
    elif args.command == "test-source":
        asyncio.run(_test_source(args.source))
    elif args.command == "oa-login":
        asyncio.run(_oa_login())


if __name__ == "__main__":
    main()
