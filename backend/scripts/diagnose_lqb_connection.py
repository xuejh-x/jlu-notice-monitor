"""Bounded transport-only probe. No database, source run or network changes."""
from __future__ import annotations

import asyncio
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import runpy
import ssl
import sys
import time
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[2]
URL = "https://lus-jlu.github.io/lqb.html"


async def main(proxy: str | None = None):
    if proxy:
        parts = urlsplit(proxy)
        if parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost"} or not parts.port or parts.username or parts.password:
            raise ValueError("Explicit probe proxy must be a credential-free HTTP loopback endpoint")
    tls = runpy.run_path(str(ROOT / "backend/app/services/tls.py"))
    rows = []
    for trust_env in ((False,) if proxy else (True, False)):
        started = time.perf_counter()
        row = {"url": URL, "time": datetime.now(timezone.utc).isoformat(), "trust_env": trust_env}
        if proxy:
            row["explicit_loopback_proxy"] = proxy
        try:
            async with httpx.AsyncClient(verify=tls["source_ssl_context"](trust_env=trust_env),
                                         trust_env=trust_env, proxy=proxy, timeout=8, follow_redirects=False) as client:
                async with client.stream("GET", URL) as response:
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 2_000_000:
                            raise ValueError("RESPONSE_SIZE_LIMIT")
                    row.update(status=response.status_code, bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                               content_type=response.headers.get("content-type"),
                               contains_lanqiao="蓝桥杯" in body.decode("utf-8", errors="replace"))
        except Exception as exc:
            parts = []
            visited = set()
            while exc is not None and id(exc) not in visited and len(parts) < 8:
                visited.add(id(exc))
                # Do not log proxy URLs, credentials or other environment values.
                parts.append({"type": type(exc).__name__, "ssl_reason": getattr(exc, "reason", None),
                              "errno": getattr(exc, "errno", None)})
                exc = exc.__cause__ or exc.__context__
            row["error_chain"] = parts
        row["seconds"] = round(time.perf_counter() - started, 3)
        rows.append(row)
        await asyncio.sleep(1)
    report = {"time": datetime.now(timezone.utc).isoformat(), "python": sys.version.split()[0],
              "openssl": ssl.OPENSSL_VERSION, "httpx": httpx.__version__,
              "environment_presence": {key: bool(os.environ.get(key)) for key in
                                       ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR")},
              "attempts": rows, "database_imports": 0, "network_setting_changes": 0,
              "limits": "Two default/direct probes or one explicit loopback proxy probe; not the installed client's process environment."}
    output = ROOT / "docs" / ("lqb-connection-proxy-diagnostic.json" if proxy else "lqb-connection-diagnostic.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proxy", help="One opt-in probe through an existing HTTP loopback proxy")
    asyncio.run(main(parser.parse_args().proxy))
