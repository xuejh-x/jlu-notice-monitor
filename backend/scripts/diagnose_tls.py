"""Read-only TLS comparison; never starts the app or opens its database.

Run from backend with .venv/Scripts/python scripts/diagnose_tls.py --output ...
An optional --openssl executable captures the server-sent chain while verifying
against certifi. --pip-truststore is for diagnosis before installing truststore.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
from urllib.parse import urlsplit

import certifi
import httpx
import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--openssl")
    parser.add_argument("--pip-truststore", action="store_true")
    parser.add_argument("--origin-check", action="store_true", help="Compare system DNS with validated Cloudflare DNS-over-HTTPS and origin TLS")
    args = parser.parse_args()
    if args.origin_check and not args.openssl:
        parser.error("--origin-check requires --openssl for certificate decoding")
    if args.pip_truststore:
        from pip._vendor import truststore
    else:
        import truststore

    configs = yaml.safe_load((Path(__file__).resolve().parents[1] / "config/sources.yaml").read_text(encoding="utf-8"))["sources"]
    targets = [(item["code"], item["sections"][0]["url"]) for item in configs if item["code"] != "lqb"]
    targets.append(("reported_innovation_spelling", "https://cxcjyxy.jlu.edu.cn/index/tzgg.htm"))

    def probe(target: tuple[str, str]) -> dict:
        code, url = target
        host = urlsplit(url).hostname
        result = {"source": code, "url": url, "requests": {}}
        try:
            result["dns"] = sorted({info[4][0] for info in socket.getaddrinfo(host, 443)})
        except OSError as exc:
            result["dns_error"] = str(exc)
        for mode in ("httpx_default", "certifi_direct", "stdlib_system", "native_system"):
            try:
                context = (
                    True if mode == "httpx_default"
                    else ssl.create_default_context(cafile=certifi.where()) if mode == "certifi_direct"
                    else ssl.create_default_context() if mode == "stdlib_system"
                    else truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                )
                with httpx.Client(verify=context, trust_env=mode == "httpx_default", timeout=12, follow_redirects=True) as client:
                    response = client.get(url)
                    result["requests"][mode] = {
                        "status": response.status_code, "bytes": len(response.content),
                        "redirects": [{"status": r.status_code, "url": str(r.url), "location": r.headers.get("location")} for r in response.history],
                        "final_url": str(response.url), "date": response.headers.get("date"),
                    }
            except Exception as exc:
                result["requests"][mode] = {"error": type(exc).__name__, "message": str(exc)}
        if args.openssl and "dns_error" not in result:
            try:
                process = subprocess.run(
                    [args.openssl, "s_client", "-connect", f"{host}:443", "-servername", host,
                     "-showcerts", "-verify_return_error", "-verify_hostname", host, "-CAfile", certifi.where()],
                    input="", capture_output=True, text=True, timeout=18,
                )
                certs = re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", process.stdout, re.S)
                chain = []
                for pem in certs:
                    decoded = subprocess.run(
                        [args.openssl, "x509", "-noout", "-subject", "-issuer", "-dates", "-fingerprint", "-sha256", "-ext", "subjectAltName,authorityInfoAccess"],
                        input=pem, capture_output=True, text=True, check=True,
                    )
                    chain.append(decoded.stdout.strip())
                result["openssl"] = {"exit_code": process.returncode, "sent_chain": chain, "verification": process.stderr.strip()}
            except Exception as exc:
                result["openssl"] = {"error": str(exc)}
        if args.origin_check:
            try:
                with httpx.Client(verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), trust_env=False, timeout=12) as client:
                    dns = client.get("https://cloudflare-dns.com/dns-query", params={"name": host, "type": "A"}, headers={"Accept": "application/dns-json"})
                    dns.raise_for_status()
                    addresses = [row["data"] for row in dns.json().get("Answer", []) if row["type"] == 1]
                result["public_dns"] = addresses
                result["native_sent_chains"] = {}
                for address in [host, *addresses[:1]]:
                    with socket.create_connection((address, 443), timeout=12) as raw:
                        with truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT).wrap_socket(raw, server_hostname=host) as secured:
                            # This API returns the actual server-sent chain, not
                            # the chain constructed by Windows from AIA/cache.
                            chain = secured.get_unverified_chain()
                            result["native_sent_chains"][address] = [
                                subprocess.run([args.openssl, "x509", "-noout", "-subject", "-issuer", "-dates", "-fingerprint", "-sha256"], input=ssl.DER_cert_to_PEM_cert(der), text=True, capture_output=True, check=True).stdout.strip()
                                for der in chain
                            ]
            except Exception as exc:
                result["origin_check_error"] = str(exc)
        return result

    variables = ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY")
    report = {
        "utc_time": datetime.now(timezone.utc).isoformat(), "python": sys.version,
        "openssl": ssl.OPENSSL_VERSION, "httpx": httpx.__version__, "certifi": certifi.__version__,
        "certifi_exists": Path(certifi.where()).is_file(), "default_verify_paths": ssl.get_default_verify_paths()._asdict(),
        "truststore": "pip-vendored diagnostic only" if args.pip_truststore else importlib.metadata.version("truststore"),
        "environment": {name: re.sub(r"(?<=://)[^/@]+@", "[REDACTED]@", os.environ[name]) if name in os.environ else None for name in variables},
    }
    with ThreadPoolExecutor(max_workers=3) as pool:
        report["targets"] = list(pool.map(probe, targets))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
