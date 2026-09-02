from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeSourceUrl(ValueError):
    pass


def validate_url_syntax(url: str) -> str:
    value = url.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeSourceUrl("Only http:// and https:// source URLs are supported")
    if not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeSourceUrl("Source URL must have a host and must not contain credentials")
    if len(value) > 2000:
        raise UnsafeSourceUrl("Source URL is too long")
    return value


def _unsafe_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


async def validate_source_url(url: str, *, allow_private_network: bool = False) -> str:
    value = validate_url_syntax(url)
    host = urlsplit(value).hostname
    assert host is not None
    try:
        direct = ipaddress.ip_address(host)
        addresses = [str(direct)]
    except ValueError:
        try:
            records = await asyncio.to_thread(socket.getaddrinfo, host, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise UnsafeSourceUrl("Source host could not be resolved") from exc
        addresses = sorted({record[4][0] for record in records})
    if not addresses:
        raise UnsafeSourceUrl("Source host did not resolve to an address")
    if not allow_private_network and any(_unsafe_address(address) for address in addresses):
        raise UnsafeSourceUrl("Local and private network addresses are not allowed for this source")
    return value
