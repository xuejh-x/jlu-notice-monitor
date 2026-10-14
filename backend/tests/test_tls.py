from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import threading
import ipaddress

import certifi
import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.crawler.runner as runner_module
import app.services.tls as tls_module
import app.sources.base as base_module
import app.sources.generic as generic_module
from app.crawler.runner import CrawlerManager
from app.database import Base
from app.models import Notice, Source, UserState
from app.services.tls import source_ssl_context
from app.sources.base import SourceError, StaticHTMLSource
from app.sources.generic import SafeFetcher

FIXTURES = Path(__file__).parent / "fixtures/tls"


@pytest.fixture(scope="session")
def generated_tls_fixtures(tmp_path_factory):
    """Create fresh loopback keys in pytest temp storage; publish no private key."""
    directory = tmp_path_factory.mktemp("tls-certificates")
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Ephemeral test CA")])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=365))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
              key_encipherment=False, data_encipherment=False, key_agreement=False,
              key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
          .sign(ca_key, hashes.SHA256()))
    (directory / "root.crt").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (directory / "server.key").write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    for name in ["valid", "expired", "wrong-host"]:
        sans = [x509.DNSName("wronghost.invalid")] if name == "wrong-host" else [
            x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
        begin = now - timedelta(days=3 if name == "expired" else 1)
        end = now - timedelta(days=2) if name == "expired" else now + timedelta(days=30)
        cert = (x509.CertificateBuilder()
                .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Loopback test")]))
                .issuer_name(ca_name).public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(begin).not_valid_after(end)
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.SubjectAlternativeName(sans), critical=False)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
                .sign(ca_key, hashes.SHA256()))
        (directory / (name + ".crt")).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return directory


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = (
            f'<ul><li><a href="/notice.htm">TLS recovery notice</a> {date.today()}</li></ul>'
            if self.path == "/list"
            else '<h1>TLS recovery notice</h1><div class="v_news_content">Verified notice body for recovery and deduplication.</div>'
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        pass


@contextmanager
def tls_server(certificate: str):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(FIXTURES / f"{certificate}.crt", FIXTURES / "server.key")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield f"https://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.fixture(autouse=True)
def no_ca_overrides(monkeypatch: pytest.MonkeyPatch, generated_tls_fixtures) -> None:
    monkeypatch.setattr(__import__(__name__, fromlist=["FIXTURES"]), "FIXTURES", generated_tls_fixtures)
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")


def trusted_context() -> ssl.SSLContext:
    context = source_ssl_context(trust_env=False)
    context.load_verify_locations(cafile=str(FIXTURES / "root.crt"))
    return context


@pytest.mark.asyncio
@pytest.mark.parametrize("certificate,trust_root,accepted", [
    ("valid", True, True), ("valid", False, False),
    ("expired", True, False), ("wrong-host", True, False),
])
async def test_real_tls_validation(certificate: str, trust_root: bool, accepted: bool) -> None:
    context = trusted_context() if trust_root else source_ssl_context(trust_env=False)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    with tls_server(certificate) as url:
        async with httpx.AsyncClient(verify=context, trust_env=False, timeout=3) as client:
            if accepted:
                assert (await client.get(url + "/list")).status_code == 200
            else:
                with pytest.raises(httpx.ConnectError) as error:
                    await client.get(url + "/list")
                cause: BaseException | None = error.value
                while cause is not None and not isinstance(cause, ssl.SSLCertVerificationError):
                    cause = cause.__cause__ or cause.__context__
                assert isinstance(cause, ssl.SSLCertVerificationError)


def test_ca_environment_override_is_exclusive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSL_CERT_FILE", str(FIXTURES / "root.crt"))
    monkeypatch.setenv("SSL_CERT_DIR", "must-not-be-used")
    context = source_ssl_context()
    assert type(context) is ssl.SSLContext
    assert context.cert_store_stats()["x509_ca"] == 1
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    monkeypatch.setenv("SSL_CERT_FILE", "missing-ca-file.crt")
    with pytest.raises(FileNotFoundError):
        source_ssl_context()
    # Cloud's trust_env=False still ignores local CA overrides.
    assert source_ssl_context(trust_env=False).check_hostname


def test_ca_directory_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSL_CERT_DIR", str(FIXTURES))
    assert type(source_ssl_context()) is ssl.SSLContext


def test_non_windows_keeps_certifi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tls_module.sys, "platform", "linux")
    context = source_ssl_context()
    expected = ssl.create_default_context(cafile=certifi.where())
    assert context.get_ca_certs(binary_form=True) == expected.get_ca_certs(binary_form=True)


@pytest.mark.asyncio
async def test_generic_fetcher_verifies_and_reports_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    with tls_server("valid") as url:
        fetcher = SafeFetcher(allow_private_network=True)
        try:
            with pytest.raises(SourceError, match="TLS_CERTIFICATE_VERIFY_FAILED"):
                await fetcher.get(url + "/list")
        finally:
            await fetcher.close()
        monkeypatch.setattr(generic_module, "source_ssl_context", lambda **_: trusted_context())
        fetcher = SafeFetcher(allow_private_network=True)
        try:
            body, _, final_url = await fetcher.get(url + "/list")
            assert "TLS recovery notice" in body and final_url == url + "/list"
        finally:
            await fetcher.close()


@pytest.mark.asyncio
async def test_tls_failure_recovers_without_resetting_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tls_server("valid") as url, Session(create_engine("sqlite:///:memory:"), expire_on_commit=False) as db:
        Base.metadata.create_all(db.get_bind())
        source = Source(code="tls", name="TLS", base_url=url)
        db.add(source)
        db.commit()
        config = {"code": "tls", "parser": "cse", "name": "TLS", "base_url": url, "sections": [{"url": url + "/list"}]}
        monkeypatch.setattr(base_module, "source_ssl_context", trusted_context)
        adapter = StaticHTMLSource(config)
        try:
            item = (await adapter.fetch_list())[0]
            detail = await adapter.fetch_detail(item)
        finally:
            await adapter.close()
        CrawlerManager._persist_candidate(db, source, detail, True)
        db.commit()
        original = db.scalar(select(Notice))
        assert original is not None and original.status == "baseline"
        original_id = original.id
        assert db.scalar(select(UserState)).is_read

        manager = CrawlerManager(cache_dir=tmp_path)
        monkeypatch.setattr(runner_module, "SessionLocal", lambda: db)
        monkeypatch.setattr(base_module, "source_ssl_context", lambda: source_ssl_context(trust_env=False))
        failed = await manager._run_source(config, False)
        assert failed.status == "failure"
        source = db.scalar(select(Source))
        assert source.last_error_code == "SOURCE_ERROR"
        assert source.last_error and "TLS_CERTIFICATE_VERIFY_FAILED" in source.last_error

        monkeypatch.setattr(base_module, "source_ssl_context", trusted_context)
        for _ in range(2):
            recovered = await manager._run_source(config, False)
            assert recovered.status == "success"
            assert recovered.new_count == 0 and recovered.unchanged_count == 1
            assert recovered.detail_skipped == 1
        source = db.scalar(select(Source))
        assert source.health_state == "healthy"
        assert source.last_error_code is None and source.last_error is None
        assert source.consecutive_errors == 0
        assert db.scalars(select(Notice.id)).all() == [original_id]
        assert db.scalar(select(UserState)).is_read
        assert db.scalar(select(Notice.status)) == "baseline"
