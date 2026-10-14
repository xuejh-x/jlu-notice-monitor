"""Read-only OA adapter probe; optional socket-only Windows interface comparison.

No application startup, database writes, system route/proxy changes, or TLS bypass.
The interface/origin parameters are diagnostic inputs, never production defaults.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import socket
import ssl
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import certifi

from app.config import load_yaml
from app.services.http_diagnostics import exception_summary
from app.services.tls import source_ssl_context
from app.sources.cloud import CloudFeedSource
from app.sources.oa_public import OAPublicSource


class VerifiedInterfaceTransport(httpx.AsyncBaseTransport):
    """Use a caller-selected interface only in this standalone diagnostic."""

    def __init__(self, origin: str, interface: int, context: ssl.SSLContext) -> None:
        self.origin = origin
        self.interface = interface
        self.context = context

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != "oa.jlu.edu.cn" or request.url.scheme != "https":
            raise ValueError("Interface probe is restricted to HTTPS OA requests")
        body = await request.aread()

        def send() -> httpx.Response:
            connection = http.client.HTTPConnection(request.url.host, 443, timeout=8)
            try:
                raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    raw.settimeout(8)
                    # Windows IP_UNICAST_IF must be set before connect().
                    raw.setsockopt(socket.IPPROTO_IP, 31, socket.htonl(self.interface))
                    raw.connect((self.origin, 443))
                    connection.sock = self.context.wrap_socket(
                        raw, server_hostname=request.url.host,
                    )
                except BaseException:
                    raw.close()
                    raise
                connection.request(request.method, request.url.raw_path.decode("ascii"),
                                   body=body, headers=dict(request.headers))
                response = connection.getresponse()
                return httpx.Response(response.status, headers=response.getheaders(),
                                      content=response.read())
            except (OSError, http.client.HTTPException) as exc:
                raise httpx.ConnectError(str(exc), request=request) from exc
            finally:
                connection.close()

        return await asyncio.to_thread(send)


async def probe(config: dict, interface: int | None, origin: str | None, *, certifi_only: bool = False) -> dict:
    adapter = OAPublicSource(config)
    if interface:
        await adapter.client.aclose()
        adapter.client = httpx.AsyncClient(
            transport=VerifiedInterfaceTransport(
                str(origin), interface,
                ssl.create_default_context(cafile=certifi.where()) if certifi_only else source_ssl_context(),
            ), timeout=8,
            follow_redirects=True,
        )
    adapter.retries = 0  # Comparison is one attempt per path, not a live crawl.
    started = time.perf_counter()
    result: dict = {"mode": (f"interface:{interface}:certifi" if certifi_only else f"interface:{interface}:native") if interface else "default",
                    "tls_verification": "CERT_REQUIRED + hostname + original SNI",
                    "http_responses": []}
    async def observe(response: httpx.Response) -> None:
        await response.aread()
        result["http_responses"].append({
            "method": response.request.method, "path": response.request.url.path,
            "status": response.status_code, "bytes": len(response.content),
        })
    adapter.client.event_hooks["response"] = [observe]
    try:
        items = await adapter.fetch_list()
        result["list_items"] = len(items)
        if not items:
            raise RuntimeError("OA list parser returned no candidates")
        detail = await adapter.fetch_detail(items[0])
        result.update(status="success", content_length=len(detail.content),
                      attachments=len(detail.attachments))
    except Exception as exc:
        result.update(status="failure", error=exception_summary(exc))
    finally:
        await adapter.close()
        result["seconds"] = round(time.perf_counter() - started, 3)
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interface-index", type=int)
    parser.add_argument("--origin-address")
    args = parser.parse_args()
    if bool(args.interface_index) != bool(args.origin_address):
        parser.error("--interface-index and --origin-address must be supplied together")
    if args.interface_index and sys.platform != "win32":
        parser.error("Interface comparison requires Windows")
    config = next(c for c in load_yaml("sources.yaml")["sources"] if c["code"] == "oa")
    # Constructor/HTTP only. Never call fetch_list(), which persists feed cursors.
    try:
        cloud = CloudFeedSource(config)
    except Exception as exc:
        cloud_result = {"status": "failure", "request_sent": False, "error": exception_summary(exc)}
    else:
        cloud_result = {"status": "configured_not_fetched", "request_sent": False}
        await cloud.close()
    comparisons = [probe(config, None, None)]
    if args.interface_index:
        comparisons.append(probe(config, args.interface_index, args.origin_address))
        comparisons.append(probe(config, args.interface_index, args.origin_address, certifi_only=True))
    report = {"utc_time": datetime.now(timezone.utc).isoformat(),
              "cloud": cloud_result, "local": await asyncio.gather(*comparisons)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
