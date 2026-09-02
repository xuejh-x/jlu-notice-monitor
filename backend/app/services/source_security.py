from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Literal
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


def unsafe_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _direct_address(host: str) -> str | None:
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return None


async def validate_local_source_url(url: str, *, allow_private_network: bool = False) -> str:
    """Validate a source owned and fetched by the local Desktop.

    Hostname DNS answers are deliberately not classified here. Desktop traffic may
    use a system proxy/VPN Fake-IP resolver, so an otherwise normal hostname can
    resolve locally to a reserved address even though the proxy fetches the public
    site. Direct IP literals and explicit localhost names remain protected.
    """

    value = validate_url_syntax(url)
    host = urlsplit(value).hostname
    assert host is not None
    normalized_host = host.rstrip(".").lower()
    if not allow_private_network and (
        normalized_host == "localhost" or normalized_host.endswith(".localhost")
    ):
        raise UnsafeSourceUrl("Local and private network addresses are not allowed for this source")
    direct = _direct_address(host)
    if not allow_private_network and direct is not None and unsafe_address(direct):
        raise UnsafeSourceUrl("Local and private network addresses are not allowed for this source")
    return value


async def validate_cloud_source_url(url: str, *, allow_private_network: bool = False) -> str:
    """Apply the strict DNS/IP boundary required for Cloud-owned fetching."""

    value = validate_url_syntax(url)
    host = urlsplit(value).hostname
    assert host is not None
    direct = _direct_address(host)
    if direct is not None:
        addresses = [direct]
    else:
        try:
            records = await asyncio.to_thread(socket.getaddrinfo, host, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise UnsafeSourceUrl("Source host could not be resolved") from exc
        addresses = sorted({record[4][0] for record in records})
    if not addresses:
        raise UnsafeSourceUrl("Source host did not resolve to an address")
    if not allow_private_network and any(unsafe_address(address) for address in addresses):
        raise UnsafeSourceUrl("Local and private network addresses are not allowed for this source")
    return value


async def validate_source_url(
    url: str,
    *,
    allow_private_network: bool = False,
    validation_scope: Literal["local", "cloud"] = "cloud",
) -> str:
    """Compatibility entry point; strict Cloud validation remains the default."""

    validator = validate_local_source_url if validation_scope == "local" else validate_cloud_source_url
    return await validator(url, allow_private_network=allow_private_network)


def validate_peer_address(address: object, *, allow_private_network: bool = False) -> None:
    """Validate the connected peer when the HTTP transport exposes it.

    DNS is validated before connect; this second boundary rejects a rebinding result
    before response bytes are consumed.
    """

    if allow_private_network or address is None:
        return
    value = address[0] if isinstance(address, tuple) and address else address
    if isinstance(value, str) and unsafe_address(value):
        raise UnsafeSourceUrl("The connected address is not allowed for this source")
