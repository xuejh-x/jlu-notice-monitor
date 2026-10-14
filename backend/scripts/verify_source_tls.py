"""Fetch real lists/details with the source adapters without touching a database."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_yaml
from app.sources import build_source


async def main() -> None:
    results = []
    for config in load_yaml("sources.yaml")["sources"]:
        adapter = build_source(config)
        result = {"source": config["code"]}
        try:
            items = await adapter.fetch_list()
            # Single-page monitors intentionally return no notice candidates.
            result["list_items"] = len(items)
            if items:
                details = []
                for item in items[:3]:
                    detail = await adapter.fetch_detail(item)
                    details.append({"url": detail.url, "content_length": len(detail.content), "attachments": len(detail.attachments)})
                    if detail.content:
                        break
                result["details"] = details
                if not any(detail["content_length"] for detail in details):
                    raise RuntimeError("Parsed detail is empty")
            elif getattr(adapter, "snapshot", None) is None:
                raise RuntimeError("Parsed list is empty")
            result["status"] = "PASS"
        except Exception as exc:
            result.update(status="FAIL", error=f"{type(exc).__name__}: {exc}")
        finally:
            await adapter.close()
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    report = {"utc_time": datetime.now(timezone.utc).isoformat(), "results": results}
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if any(item["status"] != "PASS" for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
