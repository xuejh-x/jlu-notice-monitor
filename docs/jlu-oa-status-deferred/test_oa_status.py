import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes import sources
from app.api.source_management import _serialize_source
from app.database import Base
from app.models import Source
from app.sources.cloud import is_public_feed_not_configured


@pytest.mark.parametrize("message", [
    "SourceError: GET https://oa.jlu.edu.cn/list failed: SSLEOFError: UNEXPECTED_EOF_WHILE_READING <- SourceError: PUBLIC_FEED_NOT_CONFIGURED",
    "SourceError: local timeout <- SourceError: PUBLIC_FEED_NOT_CONFIGURED",
    "cloud:SourceError: PUBLIC_FEED_NOT_CONFIGURED | local: parse error",
])
def test_cloud_missing_in_context_does_not_hide_actual_local_failure(message):
    assert not is_public_feed_not_configured("SOURCE_ERROR", message)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            source = Source(code="oa", name="OA", base_url="https://oa.jlu.edu.cn", ownership="OFFICIAL_CLOUD",
                            health_state="source_error", last_error_code="SOURCE_ERROR", last_error=message)
            db.add(source)
            db.commit()
            configured = _serialize_source(source)
            public = sources(db)[0]
            assert configured["health_state"] == "source_error" and configured["last_error"] == message
            assert public["health_state"] == public["status"] == "source_error" and public["message"] == message
    finally:
        engine.dispose()


@pytest.mark.parametrize("code,message", [("PUBLIC_FEED_NOT_CONFIGURED", None), ("SOURCE_ERROR", "SourceError: PUBLIC_FEED_NOT_CONFIGURED"), (None, "PUBLIC_FEED_NOT_CONFIGURED")])
def test_pure_missing_cloud_configuration_remains_neutral(code, message):
    assert is_public_feed_not_configured(code, message)
